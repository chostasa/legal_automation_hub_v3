import dropbox.oauth

APP_KEY = "3rnckq3k8jx0itk"
APP_SECRET = "1297a23r463j9g4"

auth_flow = dropbox.oauth.DropboxOAuth2FlowNoRedirect(
    APP_KEY,
    APP_SECRET,
    token_access_type="offline"  # This ensures you get a refresh token
)

# Paste your authorization code here
auth_code = input("kZSSkXp_j-IAAAAAAAAAjA-HXaB9T9OxHYuj6yc48Jk").strip()

# Exchange it for tokens
oauth_result = auth_flow.finish(auth_code)

print("\n✅ ACCESS TOKEN:", oauth_result.access_token)
print("✅ REFRESH TOKEN:", oauth_result.refresh_token)
print("⏳ Expires in:", oauth_result.expires_in, "seconds")
