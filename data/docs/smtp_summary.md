# SMTP Protocol Summary

## Overview

SMTP (Simple Mail Transfer Protocol) is a text-based application-layer protocol used for email transmission (RFC 5321).  
Default port: 25 (server-to-server), 587 (submission), 465 (SMTPS).  
Session flow: greeting → capability negotiation → authentication (optional) → mail transaction → quit.

---

## Connection & Session Initiation

- Server sends 220 banner on connect
- Client sends `EHLO` (or `HELO` for legacy) with client hostname
- Server responds `250` with list of extensions (on `EHLO`)
- Client may issue `STARTTLS` to upgrade to TLS

## Authentication (Optional)

- `AUTH PLAIN` / `AUTH LOGIN` / `AUTH CRAM-MD5` after EHLO
- Server responds `235` on success, `535` on failure
- `AUTH` requires prior `EHLO`

## Mail Transaction

- `MAIL FROM:<sender@domain>` — initiates envelope; server responds `250`
- `RCPT TO:<recipient@domain>` — adds recipient; can be repeated; `250` on acceptance, `550` on rejection
- `DATA` — begins message body; server responds `354`
- Client sends message content ending with a line containing only `.`
- Server responds `250` on successful queuing
- `RSET` — aborts current transaction, returns to post-EHLO state

## Session Control

- `NOOP` — keep-alive; server responds `250`
- `VRFY <address>` — verify mailbox exists; `252` or `550`
- `EXPN <list>` — expand mailing list; often disabled
- `QUIT` — terminates session; server responds `221`

---

## Key Response Codes

| Code | Meaning                          |
|------|----------------------------------|
| 220  | Service ready (banner)           |
| 221  | Service closing transmission     |
| 235  | Authentication successful        |
| 250  | Requested mail action OK         |
| 251  | User not local, will forward     |
| 252  | Cannot VRFY, will attempt        |
| 354  | Start mail input                 |
| 421  | Service not available            |
| 450  | Mailbox unavailable (try later)  |
| 500  | Syntax error                     |
| 501  | Syntax error in parameters       |
| 503  | Bad sequence of commands         |
| 535  | Authentication credentials invalid |
| 550  | Mailbox unavailable              |
| 554  | Transaction failed               |

---

## Message Types (Commands)

`EHLO`, `HELO`, `MAIL`, `RCPT`, `DATA`, `RSET`, `QUIT`, `NOOP`, `VRFY`, `EXPN`, `AUTH`, `STARTTLS`

---

## State Machine (Simplified)

```
INIT → [220 banner received] → CONNECTED
CONNECTED → [EHLO/HELO] → GREETED
GREETED → [AUTH] → AUTHENTICATED
GREETED → [MAIL FROM] → MAIL_PENDING
AUTHENTICATED → [MAIL FROM] → MAIL_PENDING
MAIL_PENDING → [RCPT TO] → RCPT_PENDING
RCPT_PENDING → [RCPT TO] → RCPT_PENDING  (multiple recipients)
RCPT_PENDING → [DATA] → DATA_PENDING
DATA_PENDING → [. (end)] → MESSAGE_SENT
MESSAGE_SENT → [MAIL FROM] → MAIL_PENDING (new transaction)
MESSAGE_SENT → [QUIT] → CLOSED
GREETED → [RSET] → GREETED
MAIL_PENDING → [RSET] → GREETED
RCPT_PENDING → [RSET] → GREETED
```

---

## Field Constraints & Ordering Rules

1. `EHLO` or `HELO` MUST precede `MAIL FROM`
2. `MAIL FROM` MUST precede `RCPT TO`
3. `RCPT TO` MUST precede `DATA`
4. At least one `RCPT TO` required before `DATA`
5. `RSET` returns to post-greeting state without closing connection
6. `AUTH` must follow `EHLO` (not `HELO`)
7. `STARTTLS` must follow `EHLO` and precede `AUTH` or `MAIL`
