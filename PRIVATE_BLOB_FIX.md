# Private Blob read fix

This build corrects Vercel Private Blob reads.

The previous BlobFix build called `BlobClient.get(url)` without `access='private'`.
On a private Blob store that causes the blob URL request to be unauthenticated and return HTTP 403.

This build calls:

```python
client.get(url_or_path, access='private')
```

and consumes the SDK `GetBlobResult.status_code` / `GetBlobResult.stream` response.
`BLOB_READ_WRITE_TOKEN` remains the only required Blob environment variable for this setup.
