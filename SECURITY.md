# Security policy

## Credentials

Every user must supply their own OpenAlex API key. Never open an issue, pull request, discussion, screenshot, or log containing a key.

Supported credential resolution order:

1. explicit Python argument for controlled integrations;
2. `OPENALEX_API_KEY` environment variable;
3. the file named by `OPENALEX_API_KEY_FILE`;
4. project-root `OPENALEX_API_KEY.txt`.

`OPENALEX_API_KEY.txt`, `.env`, runtime databases, downloaded PDFs, and generated outputs are ignored by Git. The client sends the key in the `Authorization` header and never puts it in a URL.

Institution usernames, passwords, MFA codes, SSO tokens, VPN credentials, and browser cookies must never enter chat, project files, logs, or SQLite. Users authenticate only on official institution pages. A user running Codex or another host without an authenticated browser may manually download legally accessible PDFs and place them in the local runtime directory.

## Reporting a vulnerability

Do not publish credential exposure or a working exploit in a public issue. Use GitHub's private vulnerability reporting feature for the repository. Include affected version, reproduction conditions, impact, and a proposed mitigation when available.

## Supported release

The current supported line is the latest tagged MVP release. Earlier untagged development snapshots may not receive security fixes.
