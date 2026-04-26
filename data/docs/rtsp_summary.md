# RTSP Protocol Summary

## Overview

RTSP (Real Time Streaming Protocol) is a text-based application-layer control protocol for multimedia streaming (RFC 2326 / RFC 7826).  
Default port: 554 (standard), 8554 (alternative).  
RTSP controls streaming sessions; actual media data travels over RTP/RTCP on separate channels.

---

## Session Flow

1. Client sends `OPTIONS` to discover server capabilities
2. Client sends `DESCRIBE` to get session description (SDP)
3. Client sends `SETUP` to allocate resources and establish transport
4. Client sends `PLAY` to begin media delivery
5. Client sends `PAUSE` (optional) to pause playback
6. Client sends `TEARDOWN` to release session

---

## Methods (Request Types)

| Method     | Direction       | Description                                  |
|------------|-----------------|----------------------------------------------|
| OPTIONS    | C→S or S→C      | Query supported methods                      |
| DESCRIBE   | C→S             | Retrieve session description (SDP)           |
| ANNOUNCE   | C→S or S→C      | Post/update session description              |
| SETUP      | C→S             | Allocate resources for stream transport      |
| PLAY       | C→S             | Begin or resume media delivery               |
| PAUSE      | C→S             | Temporarily halt media delivery              |
| RECORD     | C→S             | Begin recording stream                       |
| REDIRECT   | S→C             | Redirect client to new URI                   |
| TEARDOWN   | C→S             | Free resources for stream; end session       |
| GET_PARAMETER | C→S or S→C  | Retrieve parameter of presentation/stream    |
| SET_PARAMETER | C→S or S→C  | Set parameter of presentation/stream         |

---

## Header Fields

- `CSeq` — mandatory; monotonically increasing sequence number per method
- `Session` — session identifier assigned by server after SETUP
- `Transport` — transport parameters (RTP/UDP, RTP/TCP, etc.)
- `Range` — NPT or clock range for PLAY/PAUSE/RECORD
- `Content-Type` — media type of body (e.g., `application/sdp`)
- `Content-Length` — byte length of message body
- `User-Agent` — client identification
- `Public` — in OPTIONS response; lists supported methods

---

## Key Response Codes

| Code | Meaning                          |
|------|----------------------------------|
| 200  | OK                               |
| 201  | Created                          |
| 250  | Low on Storage Space             |
| 301  | Moved Permanently                |
| 302  | Moved Temporarily                |
| 400  | Bad Request                      |
| 401  | Unauthorized                     |
| 403  | Forbidden                        |
| 404  | Not Found                        |
| 405  | Method Not Allowed               |
| 406  | Not Acceptable                   |
| 451  | Parameter Not Understood         |
| 454  | Session Not Found                |
| 455  | Method Not Valid in This State   |
| 457  | Invalid Range                    |
| 459  | Aggregate Operation Not Allowed  |
| 460  | Only Aggregate Operation Allowed |
| 461  | Unsupported Transport            |
| 462  | Destination Unreachable          |
| 500  | Internal Server Error            |
| 501  | Not Implemented                  |
| 503  | Service Unavailable              |
| 505  | RTSP Version Not Supported       |

---

## State Machine (Simplified)

```
INIT → [OPTIONS] → INIT  (or CONNECTED)
INIT → [DESCRIBE] → DESCRIBED
DESCRIBED → [SETUP] → READY
READY → [PLAY] → PLAYING
PLAYING → [PAUSE] → READY
PLAYING → [TEARDOWN] → INIT
READY → [TEARDOWN] → INIT
READY → [RECORD] → RECORDING
RECORDING → [TEARDOWN] → INIT
```

---

## Field Constraints & Ordering Rules

1. `CSeq` header is mandatory in every request and response
2. `SETUP` must precede `PLAY`, `PAUSE`, `RECORD`
3. `Session` header required in requests after SETUP
4. `DESCRIBE` typically precedes `SETUP` but is not strictly required
5. `OPTIONS` can be sent at any time
6. `TEARDOWN` terminates the session; Session header no longer valid
7. `Transport` header required in SETUP request
