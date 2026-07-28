On Mac you're working entirely through the Graph API — the Windows desktop tools (OneNote Batch and anything using COM interop with the OneNote 2016 app) are off the table since they drive a local Windows app that doesn't exist on macOS.

That leaves you two realistic paths:

**Use `nnote`** if you want something working quickly. It's Go, installs cleanly on Mac with `go install github.com/fatihdumanli/onen0te-cli/cmd/nnote@latest` (you'll need Go — `brew install go` if you don't have it), and handles its own OAuth on first run. Good for creating pages from files and browsing/searching. Its weakness is the download/export side is thin.

**Roll your own with curl** if you want full control and something that won't rot when a third-party repo goes unmaintained. More upfront work but it's the durable choice.

Either way, the unavoidable first step is the same: register an app in Azure (Entra ID) to get a client ID. Roughly:

1. Go to the Azure portal → App registrations → New registration.
2. Set the redirect URI to something like `http://localhost` (for the device/auth code flow).
3. Under API permissions, add Microsoft Graph delegated permissions: `Notes.ReadWrite` (or `Notes.Read` if you only want to pull down).
4. Grab the client ID.

Then you authenticate via OAuth to get a token, and hit endpoints like:

```
# list notebooks
curl -H "Authorization: Bearer $TOKEN" \
  https://graph.microsoft.com/v1.0/me/onenote/notebooks

# create a page in a section
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: text/html" \
  --data '<html><head><title>My Page</title></head><body><p>Hello</p></body></html>' \
  "https://graph.microsoft.com/v1.0/me/onenote/sections/{section-id}/pages"
```

One honest caveat on the download direction: pages come back as **HTML**, not markdown or plain text, so pulling notes down and getting clean text out takes some parsing. Uploading is the smoother direction.

The genuinely fiddly part is the OAuth token dance, not the OneNote calls themselves. Do you want me to write you a small script that handles the auth flow and gives you simple `upload`/`download` commands? If so, I'll need to know whether this is just for your own personal account (simplest — device code flow) or something shared.
