import os
import logging
from pathlib import Path
from typing import Any, Dict
import streamlit as st
from supabase import Client, create_client

logger = logging.getLogger('ats_resume_scorer')

# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------
# Streamlit secrets are read from frontend/.streamlit/secrets.toml automatically.
# For non-Streamlit contexts (or as a fallback), we also load .env from the
# project root and from backend/ (where the actual .env currently lives).
try:
    from dotenv import load_dotenv

    _PROJECT_ROOT = Path(__file__).resolve().parents[2]  # repo root
    _CANDIDATE_ENV_PATHS = [
        _PROJECT_ROOT / '.env',          # repo-root .env
        _PROJECT_ROOT / 'backend' / '.env',  # backend/.env (legacy location)
    ]
    for _env_path in _CANDIDATE_ENV_PATHS:
        if _env_path.exists():
            load_dotenv(_env_path, override=False)
            logger.debug(f'Loaded env file: {_env_path}')
except ImportError:
    pass


def _secret(key: str, section: str = 'supabase') -> str:
    """Read from env first, then fall back to st.secrets.

    Supports both flat secrets (st.secrets[key]) and sectioned secrets
    (st.secrets[section][key]).
    """
    # 1) Environment variable (highest priority)
    val = os.getenv(key, '')
    if val:
        return val

    # 2) Streamlit secrets — try sectioned first, then flat
    try:
        return st.secrets[section][key]
    except (KeyError, FileNotFoundError, AttributeError):
        pass

    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError, AttributeError):
        return ''


def _log_config_status() -> None:
    """Emit debug logs describing which source each secret came from."""
    url_source = 'env' if os.getenv('SUPABASE_URL') else (
        'st.secrets[supabase]' if _secret('SUPABASE_URL') else 'MISSING'
    )
    key_source = 'env' if os.getenv('SUPABASE_ANON_KEY') else (
        'st.secrets[supabase]' if _secret('SUPABASE_ANON_KEY') else 'MISSING'
    )
    logger.debug(f'SUPABASE_URL     found via: {url_source}')
    logger.debug(f'SUPABASE_ANON_KEY found via: {key_source}')


SUPABASE_URL = _secret('SUPABASE_URL')
SUPABASE_ANON_KEY = _secret('SUPABASE_ANON_KEY')

OAUTH_REDIRECT_URL = (
    os.getenv('AUTH_REDIRECT_URL')
    or _secret('redirect_uri', 'google_oauth')
    or 'http://localhost:8501'
)

_log_config_status()


def _missing_config() -> str | None:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return 'Supabase is not configured — set SUPABASE_URL and SUPABASE_ANON_KEY in .env or .streamlit/secrets.toml'
    return None


@st.cache_resource
def get_client() -> Client | None:
    """Cached singleton — preserves PKCE state across Streamlit reruns."""
    if _missing_config():
        return None
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def _session_dict(session, user) -> Dict[str, Any]:
    return {
        'access_token':  session.access_token,
        'refresh_token': session.refresh_token,
        'user_id':       user.id,
        'email':         user.email,
    }


def sign_in_with_password(email: str, password: str) -> Dict[str, Any]:
    err = _missing_config()
    if err:
        return {'error': err}
    try:
        resp = get_client().auth.sign_in_with_password(
            {'email': email, 'password': password}
        )
        if not resp.session or not resp.user:
            return {'error': 'Invalid credentials'}
        return _session_dict(resp.session, resp.user)
    except Exception as exc:
        logger.warning(f'sign_in_with_password failed: {exc}')
        return {'error': _humanize(exc)}


def sign_up_with_password(email: str, password: str) -> Dict[str, Any]:
    err = _missing_config()
    if err:
        return {'error': err}
    try:
        resp = get_client().auth.sign_up({'email': email, 'password': password})
        if resp.session and resp.user:
            return _session_dict(resp.session, resp.user)
        if resp.user:
            return {'pending_confirmation': True, 'email': email}
        return {'error': 'Sign-up failed'}
    except Exception as exc:
        logger.warning(f'sign_up failed: {exc}')
        return {'error': _humanize(exc)}


def google_oauth_url() -> Dict[str, Any]:
    err = _missing_config()
    if err:
        return {'error': err}
    try:
        resp = get_client().auth.sign_in_with_oauth({
            'provider': 'google',
            'options': {'redirect_to': OAUTH_REDIRECT_URL},
        })
        return {'url': resp.url}
    except Exception as exc:
        logger.warning(f'oauth url generation failed: {exc}')
        return {'error': _humanize(exc)}


def exchange_code_for_session(auth_code: str) -> Dict[str, Any]:
    """Called once after the OAuth provider redirects back with `?code=...`."""
    err = _missing_config()
    if err:
        return {'error': err}
    client = get_client()
    try:
        storage_key = f'{client.auth._storage_key}-code-verifier'
        code_verifier = client.auth._storage.get_item(storage_key) or ''
        resp = client.auth.exchange_code_for_session({
            'auth_code': auth_code,
            'code_verifier': code_verifier,
            'redirect_to': OAUTH_REDIRECT_URL,
        })
        if not resp.session or not resp.user:
            return {'error': 'OAuth exchange returned no session'}
        return _session_dict(resp.session, resp.user)
    except Exception as exc:
        logger.warning(f'exchange_code_for_session failed: {exc}')
        return {'error': _humanize(exc)}


def sign_out() -> None:
    if _missing_config():
        return
    try:
        get_client().auth.sign_out()
    except Exception as exc:
        logger.warning(f'sign_out failed: {exc}')


def _humanize(exc: Exception) -> str:
    msg = str(exc)
    # supabase errors arrive as "<status>: {json blob}" — surface the human bit
    if 'invalid_grant' in msg.lower() or 'invalid login' in msg.lower():
        return 'Wrong email or password'
    if 'user already registered' in msg.lower() or 'already been registered' in msg.lower():
        return 'An account with this email already exists — try signing in'
    if 'password should be at least' in msg.lower():
        return 'Password too short (Supabase default is 6 characters)'
    return msg