# Example: Integrating Vault with Existing Code

This document shows practical examples of updating your AgenticTA code to use Vault.

## Example 1: Update LLM Provider (NVIDIA)

### Before (using environment variables)

```python:llm/providers/nvidia.py
import os
from .base import BaseLLMProvider

class NVIDIAProvider(BaseLLMProvider):
    def __init__(self, config: dict):
        super().__init__(config)
        # OLD: Read from environment
        self.api_key = os.getenv('NVIDIA_API_KEY')
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY not set")
```

### After (using Vault with fallback)

```python:llm/providers/nvidia.py
import os
from .base import BaseLLMProvider
from vault import get_nvidia_api_key

class NVIDIAProvider(BaseLLMProvider):
    def __init__(self, config: dict):
        super().__init__(config)
        # NEW: Read from Vault (with .env fallback)
        try:
            self.api_key = get_nvidia_api_key()
        except ValueError as e:
            raise ValueError(f"NVIDIA_API_KEY not configured: {e}")
```

**Benefits:**
- ✅ Uses Vault if available
- ✅ Falls back to .env if Vault unavailable
- ✅ Same error handling
- ✅ Minimal code changes

## Example 2: Update Configuration Loader

### Before

```python:llm/config.py
import os
import yaml
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

def load_config(config_path: str = None) -> Dict[str, Any]:
    # Load YAML config
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    # Apply environment overrides
    config = _apply_env_overrides(config)
    
    return config
```

### After

```python:llm/config.py
import os
import yaml
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
from vault import get_secrets_config

load_dotenv()

def load_config(config_path: str = None) -> Dict[str, Any]:
    # Load YAML config
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    # Apply environment overrides
    config = _apply_env_overrides(config)
    
    # NEW: Load secrets from Vault
    try:
        secrets = get_secrets_config()
        if 'runtime' not in config:
            config['runtime'] = {}
        config['runtime']['secrets'] = secrets.get_all()
    except Exception as e:
        logging.warning(f"Could not load secrets from Vault: {e}")
        # Continue with environment variables (existing behavior)
    
    return config
```

## Example 3: Update Gradio UI

### Before

```python:gradioUI.py
import os
import gradio as gr
from llm.client import LLMClient

# OLD: Read API key from environment
NVIDIA_API_KEY = os.getenv('NVIDIA_API_KEY')

def initialize_app():
    client = LLMClient(api_key=NVIDIA_API_KEY)
    # ... rest of code
```

### After

```python:gradioUI.py
import os
import gradio as gr
from llm.client import LLMClient
from vault import get_nvidia_api_key

# NEW: Read from Vault (with fallback)
try:
    NVIDIA_API_KEY = get_nvidia_api_key()
except ValueError:
    # Fallback to environment for backward compatibility
    NVIDIA_API_KEY = os.getenv('NVIDIA_API_KEY')
    if not NVIDIA_API_KEY:
        raise ValueError("NVIDIA_API_KEY not configured")

def initialize_app():
    client = LLMClient(api_key=NVIDIA_API_KEY)
    # ... rest of code
```

## Example 4: Update Test Fixtures

### Before

```python:tests/conftest.py
import os
import pytest
from dotenv import load_dotenv

load_dotenv()

@pytest.fixture
def nvidia_api_key():
    """Provide NVIDIA API key for tests."""
    key = os.getenv('NVIDIA_API_KEY')
    if not key:
        pytest.skip("NVIDIA_API_KEY not set")
    return key
```

### After

```python:tests/conftest.py
import os
import pytest
from dotenv import load_dotenv
from vault import get_nvidia_api_key

load_dotenv()

@pytest.fixture
def nvidia_api_key():
    """Provide NVIDIA API key for tests."""
    try:
        # Try Vault first
        return get_nvidia_api_key()
    except:
        # Fallback to environment
        key = os.getenv('NVIDIA_API_KEY')
        if not key:
            pytest.skip("NVIDIA_API_KEY not set")
        return key
```

## Example 5: Using Multiple Secrets

### Before

```python:study_buddy_client.py
import os
from astra import AstraClient

class StudyBuddyClient:
    def __init__(self):
        self.nvidia_key = os.getenv('NVIDIA_API_KEY')
        self.astra_token = os.getenv('ASTRA_TOKEN')
        self.hf_token = os.getenv('HF_TOKEN')
        
        if not self.nvidia_key:
            raise ValueError("NVIDIA_API_KEY required")
```

### After

```python:study_buddy_client.py
import os
from astra import AstraClient
from vault import (
    get_nvidia_api_key,
    get_astra_token,
    get_hf_token
)

class StudyBuddyClient:
    def __init__(self):
        # Required secrets
        self.nvidia_key = get_nvidia_api_key()  # Raises if missing
        
        # Optional secrets (return None if missing)
        self.astra_token = get_astra_token()
        self.hf_token = get_hf_token()
```

**Cleaner and more explicit!**

## Example 6: Lazy Loading (For Performance)

If you want to load secrets only when needed:

### Implementation

```python:llm/providers/nvidia.py
from typing import Optional
from vault import get_nvidia_api_key

class NVIDIAProvider:
    def __init__(self, config: dict):
        super().__init__(config)
        self._api_key: Optional[str] = None
    
    @property
    def api_key(self) -> str:
        """Lazy load API key from Vault."""
        if self._api_key is None:
            self._api_key = get_nvidia_api_key()
        return self._api_key
    
    def make_request(self, prompt: str):
        # API key loaded on first use
        headers = {'Authorization': f'Bearer {self.api_key}'}
        # ... rest of code
```

**Benefits:**
- ✅ Only loads secret when actually needed
- ✅ Cached after first access
- ✅ More efficient for short-lived processes

## Example 7: Environment-Specific Configuration

```python:helper.py
import os
from vault import get_secrets_config

def get_environment():
    """Get current environment (dev/staging/prod)."""
    return os.getenv('ENVIRONMENT', 'development')

def load_secrets_for_environment():
    """Load secrets appropriate for current environment."""
    env = get_environment()
    
    # In production, always use Vault
    if env == 'production':
        secrets = get_secrets_config(use_vault=True)
    
    # In development, allow .env fallback
    else:
        try:
            secrets = get_secrets_config(use_vault=True)
        except:
            # Fallback to .env for local dev
            secrets = get_secrets_config(use_vault=False)
    
    return secrets
```

## Example 8: Direct Vault Access (Advanced)

For cases where you need more control:

```python:some_admin_script.py
from vault import get_vault_client

def rotate_api_key(old_key: str, new_key: str):
    """Admin script to rotate API keys in Vault."""
    vault = get_vault_client()
    
    # Read current secrets
    current = vault.get_secret('agenticta/api-keys')
    
    # Update with new key
    current['nvidia_api_key'] = new_key
    current['rotated_at'] = datetime.now().isoformat()
    current['previous_key'] = old_key[:8] + '...'  # Store prefix only
    
    # Write back to Vault
    success = vault.set_secret('agenticta/api-keys', current)
    
    if success:
        print("✓ API key rotated successfully")
        # Clear cache so next access gets new key
        vault.clear_cache()
    else:
        print("✗ Failed to rotate API key")
```

## Migration Strategy

### Phase 1: Install and Test (Day 1)
```bash
# Install dependencies
pip install -r requirements.txt

# Test connection
python scripts/vault/vault_health_check.py

# Migrate secrets
python scripts/vault/migrate_secrets_to_vault.py
```

### Phase 2: Update Critical Paths (Day 2-3)
1. Update `llm/providers/nvidia.py`
2. Update `llm/providers/openai.py`
3. Update `llm/config.py`
4. Test LLM functionality

### Phase 3: Update Secondary Code (Day 4-5)
1. Update `gradioUI.py`
2. Update `study_buddy_client.py`
3. Update test fixtures
4. Run full test suite

### Phase 4: Production Ready (Day 6-7)
1. Test in staging environment
2. Document for team
3. Set up monitoring
4. Deploy to production

## Testing Your Changes

### Unit Test Example

```python:tests/test_vault_integration.py
import pytest
from vault import get_nvidia_api_key, get_secrets_config

def test_can_load_nvidia_api_key():
    """Test that NVIDIA API key can be loaded."""
    key = get_nvidia_api_key()
    assert key is not None
    assert len(key) > 0
    assert key.startswith('nvapi-') or key.startswith('sk-')

def test_secrets_config_loads_all():
    """Test that secrets config loads multiple secrets."""
    secrets = get_secrets_config()
    
    # Check required secrets
    assert 'NVIDIA_API_KEY' in secrets
    
    # Check optional secrets (may be None)
    all_secrets = secrets.get_all()
    assert isinstance(all_secrets, dict)
    assert len(all_secrets) > 0

def test_fallback_to_env():
    """Test that fallback to environment works."""
    import os
    
    # Set environment variable
    os.environ['TEST_SECRET'] = 'test-value'
    
    # Should fall back to env when Vault doesn't have it
    # This is tested implicitly when Vault is unavailable
    pass
```

### Integration Test Example

```python:tests/test_llm_with_vault.py
import pytest
from llm.providers.nvidia import NVIDIAProvider

def test_nvidia_provider_with_vault():
    """Test NVIDIA provider loads API key from Vault."""
    provider = NVIDIAProvider({'model': 'gpt-3.5-turbo'})
    
    # Should load API key successfully
    assert provider.api_key is not None
    assert len(provider.api_key) > 0
    
    # Should be able to make requests (integration test)
    response = provider.generate("Hello, world!")
    assert response is not None
```

## Common Patterns

### Pattern 1: Graceful Degradation

```python
try:
    from vault import get_nvidia_api_key
    NVIDIA_API_KEY = get_nvidia_api_key()
except ImportError:
    # Vault module not available (old version)
    NVIDIA_API_KEY = os.getenv('NVIDIA_API_KEY')
except ValueError:
    # Vault configured but secret not found
    NVIDIA_API_KEY = os.getenv('NVIDIA_API_KEY')
    if not NVIDIA_API_KEY:
        raise ValueError("NVIDIA_API_KEY not configured")
```

### Pattern 2: Explicit Fallback

```python
from vault import get_secrets_config

# Try Vault first
try:
    secrets = get_secrets_config(use_vault=True)
    NVIDIA_API_KEY = secrets.get('NVIDIA_API_KEY')
except Exception as e:
    logger.warning(f"Vault unavailable: {e}, using environment")
    NVIDIA_API_KEY = os.getenv('NVIDIA_API_KEY')
```

### Pattern 3: Fail Fast

```python
from vault import get_nvidia_api_key

# Require Vault in production
if os.getenv('ENVIRONMENT') == 'production':
    NVIDIA_API_KEY = get_nvidia_api_key()  # Raises if not found
else:
    # Allow fallback in dev
    try:
        NVIDIA_API_KEY = get_nvidia_api_key()
    except:
        NVIDIA_API_KEY = os.getenv('NVIDIA_API_KEY')
```

## Troubleshooting

### Issue: Import Error

```python
# Error: ModuleNotFoundError: No module named 'vault'

# Solution: Make sure you're in the AgenticTA directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# Now import will work
from vault import get_secrets_config
```

### Issue: Circular Import

```python
# Error: ImportError: cannot import name 'get_secrets_config'

# Cause: Circular import between modules
# Solution: Import at function level instead of module level

def initialize_app():
    from vault import get_secrets_config  # Import here
    secrets = get_secrets_config()
    # ... use secrets
```

### Issue: Vault Unavailable in Tests

```python
# Use pytest fixtures with fallback

@pytest.fixture(scope='session')
def secrets():
    """Provide secrets for tests."""
    try:
        from vault import get_secrets_config
        return get_secrets_config()
    except:
        # Fallback for tests without Vault
        return {
            'NVIDIA_API_KEY': os.getenv('NVIDIA_API_KEY'),
            'HF_TOKEN': os.getenv('HF_TOKEN')
        }
```

---

**Ready to integrate?** Start with Example 1 (update one provider) and test thoroughly before moving on!

