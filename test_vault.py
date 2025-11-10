#%%
import sys
import hvac
import os


vault_addr = os.getenv('VAULT_ADDR', 'https://stg.internal.vault.nvidia.com')
vault_namespace = os.getenv('VAULT_NAMESPACE', 'wwfo-self-ta')
#vault_token = os.getenv('VAULT_TOKEN', 'dev-only-token')
vault_token = os.getenv('VAULT_TOKEN', 'hvs.CAESIK7sdW3fDgCBjFhd04AMmw2VPWcIIT66F9n79Ay-UziCGiMKIWh2cy5SMEVZeVRDUmhnS2dva2pTS0pGY0ZwMDguNDJmSA')


client = hvac.Client(
    url=vault_addr,
    token=vault_token,
)
print(client.is_authenticated())

#%%
create_response = client.secrets.kv.v2.create_or_update_secret(
    path='my-secret-password',
    secret=dict(password='Hashi123'),
)
print('Secret written successfully.')

#%%

read_response = client.secrets.kv.read_secret_version(path='my-secret-password')
password = read_response['data']['data']['password']
if password != 'Hashi123':
    sys.exit('unexpected password')

print('Access granted!')

# %%
