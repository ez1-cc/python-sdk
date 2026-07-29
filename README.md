# EasyOne Python SDK

Official Python SDK for interacting with EasyOne API. Provides client-side AES-GCM encryption and chunked upload functionality.

## Installation

```bash
pip install ez1-python-sdk
```

## Quick Start

```python
from pathlib import Path
from ez1 import EasyOneClient

client = EasyOneClient(
    api_key='up_live_YOUR_KEY_HERE',  # Replace with your actual API key
    base_url='https://file.ez1.cc',  # optional
)

path = Path('my-file.pdf')
with path.open('rb') as source:
    result = client.upload_file(
        source,
        file_name=path.name,
        file_size=path.stat().st_size,
        mime_type='application/pdf',
        retention_days=30,
        private=True,
    )

print(f"CID: {result['cid']}")
print(f"Decryption Key: {result['decryptionKey']}")
```

All uploads encrypt filename, MIME type, and original size as client-side metadata. Embedding is disabled by default and must be explicitly enabled with `embed=True`. Private uploads and uploads with a download limit cannot enable embedding.

## Downloading a File

```python
# Download, authenticate, and decrypt directly into a writable stream.
with open('downloaded-file.pdf', 'wb') as destination:
    metadata = client.download_file(
        result['cid'],
        result['decryptionKey'],
        destination,
    )
```

## Listing Files

```python
files = client.list_files(limit=20)

for file in files['files']:
    print(f"{file['id']} - encrypted metadata: {bool(file.get('encryptedMetadata'))}")

metadata = client.get_metadata('content-id')
if metadata.get('encryptedMetadata'):
    plain = client.decrypt_metadata(metadata['encryptedMetadata'], 'decryption-key')
    print(f"{plain['filename']} ({plain['size']} bytes)")
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
)
```

#### Methods

- `upload_file(source, *, file_name, file_size, mime_type, ...)` - Encrypt and upload a bounded-memory binary stream
- `download_file(cid, decryption_key, destination)` - Authenticate and decrypt into a binary writable stream
- `get_download_info(cid)` - Get download URL and metadata
- `get_metadata(cid)` - Get file metadata
- `list_files(limit=50, offset=0)` - List user's files
- `build_encrypted_metadata(metadata, decryption_key)` - Encrypt metadata for low-level uploads
- `decrypt_metadata(encrypted_metadata, key)` - Decrypt encrypted metadata
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

The declared upload size must exactly match the input stream. Downloads authenticate each encrypted chunk before writing its plaintext and reject truncated or trailing ciphertext.

## License

MIT
