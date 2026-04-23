# FTP Protocol Summary (Based on RFC 959)

## Overview
FTP (File Transfer Protocol) is a standard network protocol used to transfer files between a client and server over TCP.
FTP uses two separate connections: a control connection (port 21) and a data connection.

## Core Command Categories

### Authentication Commands
- **USER**: Specify the username for login. Format: `USER <username>`
- **PASS**: Specify the password. Format: `PASS <password>`. Must follow USER.
- **ACCT**: Specify account information (rarely used).

### Navigation Commands
- **PWD**: Print working directory. Returns the current directory path.
- **CWD**: Change working directory. Format: `CWD <path>`
- **CDUP**: Change to parent directory.

### File Transfer Commands
- **RETR**: Retrieve (download) a file. Format: `RETR <filename>`
- **STOR**: Store (upload) a file. Format: `STOR <filename>`
- **LIST**: List files in the current or specified directory.
- **NLST**: Name list — minimal file listing.

### Data Connection Commands
- **PASV**: Enter passive mode (server opens data port).
- **PORT**: Active mode — client specifies data port. Format: `PORT h1,h2,h3,h4,p1,p2`
- **TYPE**: Set transfer type. `TYPE A` for ASCII, `TYPE I` for binary.

### Session Commands
- **QUIT**: Terminate the session.
- **NOOP**: No operation, used as keepalive.
- **SYST**: Query the server's operating system type.
- **FEAT**: List supported features.

## Response Code Categories
- **1xx**: Positive preliminary (e.g., 150 — file status okay, opening data connection)
- **2xx**: Positive completion (e.g., 200 — command okay, 230 — logged in)
- **3xx**: Positive intermediate (e.g., 331 — need password, 350 — awaiting further info)
- **4xx**: Transient negative (e.g., 421 — service not available, 450 — file unavailable)
- **5xx**: Permanent negative (e.g., 500 — syntax error, 530 — not logged in)

## Key Protocol Rules
1. PASS must be sent after USER
2. Data transfer commands (LIST, RETR, STOR) require successful authentication
3. PASV or PORT should be sent before data transfer commands
4. QUIT can be sent from any state
5. After authentication failure, the user may retry USER
