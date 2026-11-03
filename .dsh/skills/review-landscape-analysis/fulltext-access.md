# Full-text access through open sources and institutional SSO

## Access order

For every semantically included review:

1. Check a legal open-access PDF first.
2. If no open version exists, persist `login_required`; do not silently downgrade to abstract-only evidence.
3. Call `module02-next`. It returns `request_institutional_access` and pauses for the user's numbered choice.
4. Never ask the user to type a student/staff identifier, password, MFA code, cookie, or token in chat.

## Numbered institutional-access choice

Display:

```text
未找到合法开放全文。是否尝试使用学校权限？

1. 我将在学校官方页面登录并下载PDF
2. 学校没有订阅，跳过全文
3. 不使用学校权限，按摘要继续
```

### Choice 1: institution login

- If a trusted authenticated-browser provider is available, open only the official institution/library/publisher login page. Pause while the user enters credentials directly into that page. The Agent must not inspect form fields, screenshots, cookies, or tokens.
- In Codex or another runtime without an authenticated browser, tell the user to open their normal browser, log in through the institution, download each legally accessible PDF, and place it at the suggested path under `runtime/institutional-pdfs/`.
- After the user confirms the download, register each local PDF as `institutional_downloaded` with its absolute path, source URL, license note, and access outcome.
- If some PDFs remain unavailable, keep those records at `login_required` and ask again, or let the user choose 2 or 3 for those records.

### Choice 2: no subscription

Persist `institution_not_subscribed` for the affected review, do not retry another route that evades access control, and continue with `abstract_only` or `metadata_only` evidence.

### Choice 3: abstract-only continuation

Persist `skipped` with a note that the user declined institutional access, then continue with `abstract_only` or `metadata_only` evidence.

## Never collect credentials

Do not request, read, store, log, screenshot, export, or forward:

- student/staff identifier;
- password;
- MFA code;
- SSO token;
- browser cookie;
- VPN credential.

The project database stores only the user's access choice, access outcome, source URL, PDF path/hash, and license note.

## Access outcomes

- `oa_downloaded`: legal open-access PDF downloaded.
- `institutional_downloaded`: PDF downloaded after user-completed SSO and entitlement check.
- `login_required`: open access failed and the user has not resolved institutional access.
- `institution_not_subscribed`: authentication succeeded but no full-text entitlement exists; skip immediately.
- `license_restricted`: access exists but automated analysis/download is not permitted; skip.
- `download_failed`: an allowed open download failed technically; treat it as unresolved and offer the same institutional-access choice before analysis.
- `skipped`: the user chose not to use institutional access.

`login_required` and `download_failed` are blocking states. The Python core refuses review analysis and anchor finalization until each changes to a downloaded or explicit skip/failure outcome.

## Token behavior

HTTP download and local deterministic PDF parsing consume no model tokens. Waiting while the user completes SSO consumes no model tokens. Model tokens are consumed only when the Agent is invoked or extracted PDF text/images enter a model request.

To control token use, parse locally and send only the abstract, section headings, introduction rationale, conclusion, outlook/future-work sections, and necessary evidence spans. Do not send the entire PDF when targeted sections suffice.
