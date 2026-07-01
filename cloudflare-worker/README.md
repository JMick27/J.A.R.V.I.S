# ATLAS AI Proxy

This Cloudflare Worker keeps the Gemini API key on the server. Public ATLAS
builds receive only the Worker URL.

## Deploy

1. Run `npm install` in this folder.
2. Run `npx wrangler login` and finish the browser sign-in.
3. Run `npx wrangler secret put GEMINI_API_KEY` and paste the key into Wrangler's private prompt.
4. Run `npm run deploy`.
5. Put the resulting `https://...workers.dev` URL in `distribution_config.json`.

Never add the key to `wrangler.toml`, GitHub, or the desktop application.
