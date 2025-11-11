#%%
import sys
import hvac
import os


vault_addr = os.getenv('VAULT_ADDR', 'https://stg.internal.vault.nvidia.com')
vault_namespace = os.getenv('VAULT_NAMESPACE', 'wwfo-self-ta')
vault_token = os.getenv('VAULT_TOKEN')
mount_point = os.getenv('VAULT_MOUNT_POINT', 'secret')

if not vault_token:
    print("ERROR: VAULT_TOKEN environment variable is not set")
    sys.exit(1)

# Initialize client with namespace
client = hvac.Client(
    url=vault_addr,
    token=vault_token,
    namespace=vault_namespace  # IMPORTANT: Must set namespace!
)
print(f"Authenticated: {client.is_authenticated()}")
print(f"Vault: {vault_addr}")
print(f"Namespace: {vault_namespace}")
print(f"Mount point: {mount_point}")

#%%
# Use agenticta/* path for secrets (per policy in NVIDIA_VAULT_SETUP.md)
test_path = 'agenticta/test'
create_response = client.secrets.kv.v2.create_or_update_secret(
    mount_point=mount_point,  # IMPORTANT: Must specify mount_point!
    path=test_path,
    secret=dict(password='Hashi123'),
)
print(f'Secret written successfully to {mount_point}/data/{test_path}')

#%%
read_response = client.secrets.kv.v2.read_secret_version(
    mount_point=mount_point,  # IMPORTANT: Must specify mount_point!
    path=test_path,
    raise_on_deleted_version=False  # Align with future hvac v3.0.0 default
)
password = read_response['data']['data']['password']
if password != 'Hashi123':
    sys.exit('unexpected password')

print('Access granted!')
print(f'Successfully read secret from {mount_point}/data/{test_path}')

# %%
