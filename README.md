# EasyOne Python SDK

Official Python SDK for interacting with EasyOne API. Provides client-side AES-GCM encryption and chunked upload functionality.

## Installation

```bash
pip install ez1-python-sdk
```

## Quick Start

```python
from ez1 import EasyOneClient

client = EasyOneClient(
    api_key='up_live_YOUR_KEY_HERE',  # Replace with your actual API key
    base_url='https://file.ez1.cc',  # optional
)

# Upload a file
result = client.upload_file(
    'my-file.pdf',
    options={
        'fileName': 'my-file.pdf',
        'mimeType': 'application/pdf',
        'retentionDays': 30,  # Days to keep the file (default: 30)
        # Set to 0 for indefinite retention (requires unlimited retention permission)
        'private': True,  # Basic plan or higher: encrypts metadata while keeping CID + key links shareable
    }
)

print(f"CID: {result['cid']}")
print(f"Decryption Key: {result['decryptionKey']}")
```

## Downloading a File

```python
# Download and decrypt a file
data = client.download_file(
    result['cid'],
    result['decryptionKey'],
    output_path='downloaded-file.pdf'
)
```

## Listing Files

```python
files = client.list_files(limit=20)

for file in files['files']:
    print(f"{file['filename']} - {file['size']} bytes")
```

## Encryption Only

```python
# Encrypt data without uploading
message = b'Secret message'
encrypted = client.encrypt_data(message)

# Decrypt later
decrypted = client.decrypt_data(encrypted['encrypted'], encrypted['key'])
print(decrypted.decode('utf-8'))
```

## API Reference

### `EasyOneClient`

#### Constructor

```python
EasyOneClient(
    api_key: str,
    base_url: str = None,
    chunk_size: int = None,
)
```

#### Methods

- `upload_file(file_path, options=None)` - Upload a file with encryption
- `download_file(cid, decryption_key, output_path=None)` - Download and decrypt a file
- `get_download_info(cid)` - Get download URL and metadata
- `get_metadata(cid)` - Get file metadata
- `list_files(limit=50, offset=0)` - List user's files
- `encrypt_data(data)` - Encrypt data without uploading
- `decrypt_data(encrypted_data, key)` - Decrypt data

## Security Best Practices

### API Key Storage

- Store API keys in environment variables
- Never commit keys to version control
- Use different keys for development/staging/production
- Rotate keys regularly (recommended: every 90 days)

```bash
# .env file
EASYONE_API_KEY=up_live_YOUR_KEY_HERE
```

### Decryption Key Management

- Store decryption keys in encrypted storage (e.g., AWS KMS, Azure Key Vault)
- Never log decryption keys
- Implement key rotation for encrypted files

### Client-Side Validation

The SDK now includes:
- API key format validation (must start with `up_live_`)
- File size validation (max 100GB)
- File type validation (blocks executable files)

## License

MIT
