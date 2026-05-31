# OpenShift Container Platform & Virtualization CVEs

> [!NOTE]
> The Red Hat Security Data API returns CVEs by product. Exact minor version mapping (e.g., 4.19.2 vs 4.19.3) is typically resolved at the **Errata (RHSA)** level rather than the root CVE level. The list below represents recent vulnerabilities affecting the platforms.

| CVE ID | Severity | Public Date | Description |
| :--- | :--- | :--- | :--- |
| **[CVE-2026-44604](https://access.redhat.com/security/cve/CVE-2026-44604)** | moderate | 2026-05-28 | rpm: Command injection in rpmuncompress doUntar() via unescaped archive top-level directory name in popen() shell command |
| **[CVE-2026-9804](https://access.redhat.com/security/cve/CVE-2026-9804)** | important | 2026-05-28 | kubevirt: kubevirt: VMExport directory symlink escape enables exporter pod file read |
| **[CVE-2026-8643](https://access.redhat.com/security/cve/CVE-2026-8643)** | important | 2026-05-27 | python-pip: Path traversal via malicious entry point name in pip wheel installation allows arbitrary file overwrite |
| **[CVE-2026-1933](https://access.redhat.com/security/cve/CVE-2026-1933)** | important | 2026-05-27 | samba: Missing access check on reparse point operations |
| **[CVE-2026-2340](https://access.redhat.com/security/cve/CVE-2026-2340)** | moderate | 2026-05-27 | samba: vfs_worm does not block directory modification |
| **[CVE-2026-3012](https://access.redhat.com/security/cve/CVE-2026-3012)** | important | 2026-05-27 | samba: group policy certificate enrollment uses http:// without validation |
| **[CVE-2026-48863](https://access.redhat.com/security/cve/CVE-2026-48863)** | important | 2026-05-26 | libsolv: Stack-based buffer overflow in libsolv EdDSA PGP signature verification allows denial of service |
| **[CVE-2026-48864](https://access.redhat.com/security/cve/CVE-2026-48864)** | moderate | 2026-05-26 | libsolv: Heap buffer overflow in libsolv repopagestore via unchecked decompression of malicious .solv page data |
| **[CVE-2026-4480](https://access.redhat.com/security/cve/CVE-2026-4480)** | important | 2026-05-26 | samba: Samba: Remote Code Execution in printing subsystem via unescaped job description |
| **[CVE-2026-3592](https://access.redhat.com/security/cve/CVE-2026-3592)** | moderate | 2026-05-26 | bind: Amplification vulnerabilities via self-pointed glue records |
| **[CVE-2026-5950](https://access.redhat.com/security/cve/CVE-2026-5950)** | moderate | 2026-05-26 | bind: Unbounded resend loop in BIND 9 resolver |
| **[CVE-2026-32792](https://access.redhat.com/security/cve/CVE-2026-32792)** | moderate | 2026-05-26 | unbound: Packet of death with DNSCrypt |
| **[CVE-2026-4408](https://access.redhat.com/security/cve/CVE-2026-4408)** | important | 2026-05-26 | samba: Remote Code Execution in SAMR |
| **[CVE-2026-43503](https://access.redhat.com/security/cve/CVE-2026-43503)** | important | 2026-05-23 | kernel: net: skbuff: propagate shared-frag marker through frag-transfer helpers |
| **[CVE-2026-9277](https://access.redhat.com/security/cve/CVE-2026-9277)** | important | 2026-05-22 | shell-quote: shell-quote: Arbitrary code execution via command injection due to unescaped line terminators |
| **[CVE-2026-9277](https://access.redhat.com/security/cve/CVE-2026-9277)** | important | 2026-05-22 | shell-quote: shell-quote: Arbitrary code execution via command injection due to unescaped line terminators |
| **[CVE-2026-5946](https://access.redhat.com/security/cve/CVE-2026-5946)** | important | 2026-05-21 | bind: Invalid handling of CLASS != IN |
| **[CVE-2026-3039](https://access.redhat.com/security/cve/CVE-2026-3039)** | important | 2026-05-21 | bind: BIND 9 server memory exhaustion during GSS-API TKEY negotiation |
| **[CVE-2026-5947](https://access.redhat.com/security/cve/CVE-2026-5947)** | important | 2026-05-21 | bind: SIG(0) validation during query flood may lead to undefined behavior |
| **[CVE-2026-3593](https://access.redhat.com/security/cve/CVE-2026-3593)** | important | 2026-05-21 | bind: Heap use-after-free vulnerability in BIND 9 DNS-over-HTTPS implementation |
| **[CVE-2026-9150](https://access.redhat.com/security/cve/CVE-2026-9150)** | moderate | 2026-05-20 | libsolv: Stack-based buffer overflow in libsolv's Debian metadata parser when handling SHA384/SHA512 checksums |
| **[CVE-2026-9149](https://access.redhat.com/security/cve/CVE-2026-9149)** | moderate | 2026-05-20 | libsolv: Heap buffer overflow in libsolv repo_add_solv via negative maxsize from crafted .solv file |
| **[CVE-2026-33278](https://access.redhat.com/security/cve/CVE-2026-33278)** | important | 2026-05-20 | unbound: Unbound DNSSEC Validator Use-After-Free via Deep Copy Pointer Overwrite Leading to DoS and Possible Remote Code Execution |
| **[CVE-2026-42944](https://access.redhat.com/security/cve/CVE-2026-42944)** | important | 2026-05-20 | unbound: Heap overflow and crash with multiple nsid, cookie, padding EDNS options |
| **[CVE-2026-44608](https://access.redhat.com/security/cve/CVE-2026-44608)** | moderate | 2026-05-20 | unbound: Unbound: Denial of Service due to locking inconsistency during RPZ XFR reload |
| **[CVE-2026-45232](https://access.redhat.com/security/cve/CVE-2026-45232)** | moderate | 2026-05-20 | rsync: Rsync: Denial of Service via malformed HTTP proxy response |
| **[CVE-2026-43618](https://access.redhat.com/security/cve/CVE-2026-43618)** | important | 2026-05-20 | rsync: rsync: Remote memory disclosure via integer overflow in compressed-token decoding |
| **[CVE-2026-29518](https://access.redhat.com/security/cve/CVE-2026-29518)** | important | 2026-05-20 | rsync: TOCTOU symlink race condition allowing local privilege escalation in daemon mode without chroot. |
| **[CVE-2026-43620](https://access.redhat.com/security/cve/CVE-2026-43620)** | moderate | 2026-05-20 | rsync: rsync: Remote Denial of Service via Out-of-bounds Read |
| **[CVE-2026-43619](https://access.redhat.com/security/cve/CVE-2026-43619)** | moderate | 2026-05-20 | rsync: rsync: Symlink race vulnerability allows unauthorized file operations |
| **[CVE-2026-43617](https://access.redhat.com/security/cve/CVE-2026-43617)** | moderate | 2026-05-20 | rsync: rsync: Hostname-based ACL bypass in daemon chroot configuration |
| **[CVE-2026-42959](https://access.redhat.com/security/cve/CVE-2026-42959)** | important | 2026-05-20 | unbound: Unbound DNSSEC Validator Denial of Service via Incorrect Write Offset Counter in Chase-Reply Messages |
| **[CVE-2026-42960](https://access.redhat.com/security/cve/CVE-2026-42960)** | moderate | 2026-05-20 | unbound: Unbound DNS Cache Poisoning via Promiscuous Additional Section RRSet Acceptance |
| **[CVE-2026-42923](https://access.redhat.com/security/cve/CVE-2026-42923)** | moderate | 2026-05-20 | unbound: Unbound DNSSEC Validator NSEC3 Hash Calculation Limit Bypass via Negative Cache Code Path Leading to DoS |
| **[CVE-2026-46483](https://access.redhat.com/security/cve/CVE-2026-46483)** | moderate | 2026-05-15 | vim: command injection when decompressing .tgz archives |
| **[CVE-2026-46333](https://access.redhat.com/security/cve/CVE-2026-46333)** | important | 2026-05-15 | kernel: Read root-owned files as an unprivileged user |
| **[CVE-2026-41888](https://access.redhat.com/security/cve/CVE-2026-41888)** | moderate | 2026-05-14 | github.com/distribution/distribution: Distribution: Security bypass allows unauthorized tag deletion |
| **[CVE-2026-44431](https://access.redhat.com/security/cve/CVE-2026-44431)** | moderate | 2026-05-13 | urllib3: urllib3: Information disclosure via cross-origin redirects forwarding sensitive headers |
| **[CVE-2026-44432](https://access.redhat.com/security/cve/CVE-2026-44432)** | important | 2026-05-13 | urllib3: urllib3: Denial of Service due to excessive HTTP response decompression |
| **[CVE-2026-46300](https://access.redhat.com/security/cve/CVE-2026-46300)** | important | 2026-05-13 | kernel: "Fragnesia" is a variant of Dirty Frag vulnerability in the ESP/XFRM leading to Local Privilege Escalation (LPE) vulnerability in the Linux... |
| **[CVE-2026-7168](https://access.redhat.com/security/cve/CVE-2026-7168)** | moderate | 2026-05-13 | curl: libcurl: Information disclosure via incorrect Proxy-Authorization header reuse |
| **[CVE-2026-44664](https://access.redhat.com/security/cve/CVE-2026-44664)** | moderate | 2026-05-13 | fast-xml-builder: fast-xml-builder: Arbitrary XML/HTML injection via insufficient sanitization of XML comments |
| **[CVE-2026-44665](https://access.redhat.com/security/cve/CVE-2026-44665)** | moderate | 2026-05-13 | fast-xml-builder: fast-xml-builder: Attribute injection leading to information disclosure or content manipulation |
| **[CVE-2026-44431](https://access.redhat.com/security/cve/CVE-2026-44431)** | moderate | 2026-05-13 | urllib3: urllib3: Information disclosure via cross-origin redirects forwarding sensitive headers |
| **[CVE-2026-44432](https://access.redhat.com/security/cve/CVE-2026-44432)** | important | 2026-05-13 | urllib3: urllib3: Denial of Service due to excessive HTTP response decompression |
| **[CVE-2025-35979](https://access.redhat.com/security/cve/CVE-2025-35979)** | moderate | 2026-05-12 | kernel: Kernel: Information disclosure via shared microarchitectural predictor state in Intel(R) Processors |
| **[CVE-2026-6402](https://access.redhat.com/security/cve/CVE-2026-6402)** | moderate | 2026-05-12 | webpack-dev-server: webpack-dev-server: Information disclosure due to cross-origin source code exposure |
| **[CVE-2026-6402](https://access.redhat.com/security/cve/CVE-2026-6402)** | moderate | 2026-05-12 | webpack-dev-server: webpack-dev-server: Information disclosure due to cross-origin source code exposure |
| **[CVE-2026-43896](https://access.redhat.com/security/cve/CVE-2026-43896)** | moderate | 2026-05-11 | jq: stack overflow in recursive object merge |
| **[CVE-2026-43895](https://access.redhat.com/security/cve/CVE-2026-43895)** | moderate | 2026-05-11 | jq: embedded NUL in jq import paths causes local redaction-policy bypass and preserves sensitive fields in published artifacts |
| **[CVE-2026-44777](https://access.redhat.com/security/cve/CVE-2026-44777)** | moderate | 2026-05-11 | jq: stack overflow in module loading on mutual include |
| **[CVE-2026-43894](https://access.redhat.com/security/cve/CVE-2026-43894)** | moderate | 2026-05-11 | jq: jq: Arbitrary Code Execution or Denial of Service via Signed Integer Overflow |
| **[CVE-2026-41256](https://access.redhat.com/security/cve/CVE-2026-41256)** | moderate | 2026-05-11 | jq: embedded NUL truncates top-level jq programs loaded with -f |
| **[CVE-2026-40612](https://access.redhat.com/security/cve/CVE-2026-40612)** | moderate | 2026-05-11 | jq: stack overflow via unbounded recursion in jv_contains |
| **[CVE-2026-41257](https://access.redhat.com/security/cve/CVE-2026-41257)** | moderate | 2026-05-11 | jq: signed-int overflow in stack_reallocate |
| **[CVE-2026-8261](https://access.redhat.com/security/cve/CVE-2026-8261)** | moderate | 2026-05-11 | squirrel: Squirrel: Heap-based buffer overflow allows local denial of service |
| **[CVE-2026-43500](https://access.redhat.com/security/cve/CVE-2026-43500)** | important | 2026-05-11 | kernel: "Dirty Frag" RxRPC variant is a new universal Local Privilege Escalation (LPE) vulnerability in the Linux kernel |
| **[CVE-2026-8261](https://access.redhat.com/security/cve/CVE-2026-8261)** | moderate | 2026-05-11 | squirrel: Squirrel: Heap-based buffer overflow allows local denial of service |
| **[CVE-2026-45190](https://access.redhat.com/security/cve/CVE-2026-45190)** | moderate | 2026-05-10 | Net::CIDR::Lite: perl: Net::CIDR::Lite: IP ACL bypass due to improper input validation |
| **[CVE-2026-2291](https://access.redhat.com/security/cve/CVE-2026-2291)** | moderate | 2026-05-09 | dnsmasq: dnsmasq: heap buffer overflow in cache via NAME_ESCAPE expansion |
| **[CVE-2026-4890](https://access.redhat.com/security/cve/CVE-2026-4890)** | important | 2026-05-09 | dnsmasq: NSEC bitmap parsing infinite loop |
| **[CVE-2026-4891](https://access.redhat.com/security/cve/CVE-2026-4891)** | important | 2026-05-09 | dnsmasq: RRSIG rdlen underflow leading to heap OOB read |
| **[CVE-2026-4892](https://access.redhat.com/security/cve/CVE-2026-4892)** | important | 2026-05-09 | dnsmasq: DHCPv6 CLID buffer overflow in helper process |
| **[CVE-2026-4893](https://access.redhat.com/security/cve/CVE-2026-4893)** | moderate | 2026-05-09 | dnsmasq: Broken ECS source validation bypass |
| **[CVE-2026-5172](https://access.redhat.com/security/cve/CVE-2026-5172)** | important | 2026-05-09 | dnsmasq: extract_addresses() OOB read via malformed rdlen |
| **[CVE-2026-45130](https://access.redhat.com/security/cve/CVE-2026-45130)** | moderate | 2026-05-08 | vim: Vim: Heap buffer overflow allows arbitrary code execution or denial of service |
| **[CVE-2026-6659](https://access.redhat.com/security/cve/CVE-2026-6659)** | moderate | 2026-05-08 | Crypt::PasswdMD5: Perl: Crypt::PasswdMD5: Weak cryptographic salts due to predictable random number generation |
| **[CVE-2026-41889](https://access.redhat.com/security/cve/CVE-2026-41889)** | moderate | 2026-05-08 | github.com/jackc/pgx: golang: pgx: SQL injection via specific SQL query conditions |
| **[CVE-2026-41506](https://access.redhat.com/security/cve/CVE-2026-41506)** | moderate | 2026-05-08 | golang: github.com/go-git/go-git: go-git: Information disclosure of HTTP authentication credentials via redirects |
| **[CVE-2026-41506](https://access.redhat.com/security/cve/CVE-2026-41506)** | moderate | 2026-05-08 | golang: github.com/go-git/go-git: go-git: Information disclosure of HTTP authentication credentials via redirects |
| **[CVE-2026-33811](https://access.redhat.com/security/cve/CVE-2026-33811)** | important | 2026-05-07 | net: golang: Go net package: Denial of Service via long CNAME response in LookupCNAME |
| **[CVE-2026-41139](https://access.redhat.com/security/cve/CVE-2026-41139)** | important | 2026-05-07 | mathjs: math.js: Arbitrary code execution via expression parser |
| **[CVE-2026-41674](https://access.redhat.com/security/cve/CVE-2026-41674)** | important | 2026-05-07 | xmldom: xmldom: Arbitrary XML markup injection |
| **[CVE-2026-43284](https://access.redhat.com/security/cve/CVE-2026-43284)** | important | 2026-05-07 | kernel: "Dirty Frag" ESP XFRM variant is a new universal Local Privilege Escalation (LPE) vulnerability in the Linux kernel |
| **[CVE-2026-33811](https://access.redhat.com/security/cve/CVE-2026-33811)** | important | 2026-05-07 | net: golang: Go net package: Denial of Service via long CNAME response in LookupCNAME |
| **[CVE-2026-41650](https://access.redhat.com/security/cve/CVE-2026-41650)** | moderate | 2026-05-07 | fast-xml-parser: fast-xml-parser: XML injection via improper escaping of comment and CDATA sequences |
| **[CVE-2026-44405](https://access.redhat.com/security/cve/CVE-2026-44405)** | low | 2026-05-05 | paramiko: Paramiko: Data integrity could be compromised due to SHA-1 algorithm use |
| **[CVE-2026-35579](https://access.redhat.com/security/cve/CVE-2026-35579)** | important | 2026-05-05 | github.com/coredns/coredns: CoreDNS: Authentication bypass allows unauthorized access to TSIG-protected functionalities |
| **[CVE-2026-33489](https://access.redhat.com/security/cve/CVE-2026-33489)** | moderate | 2026-05-05 | CoreDNS: github.com/coredns/coredns: CoreDNS: Information disclosure via incorrect ACL stanza selection in transfer plugin |
| **[CVE-2026-32936](https://access.redhat.com/security/cve/CVE-2026-32936)** | moderate | 2026-05-05 | github.com/coredns/coredns: CoreDNS: Denial of Service via oversized DNS-over-HTTPS GET requests |
| **[CVE-2026-32934](https://access.redhat.com/security/cve/CVE-2026-32934)** | moderate | 2026-05-05 | coredns: github.com/coredns/coredns: CoreDNS: Denial of Service due to unbounded resource growth in DNS-over-QUIC (DoQ) stream handling |
| **[CVE-2026-43869](https://access.redhat.com/security/cve/CVE-2026-43869)** | important | 2026-05-05 | Apache Thrift: Apache Thrift: Security bypass due to improper certificate validation |
| **[CVE-2026-6321](https://access.redhat.com/security/cve/CVE-2026-6321)** | important | 2026-05-04 | fast-uri: fast-uri: Path traversal vulnerability allows bypass of security policies |
| **[CVE-2026-33846](https://access.redhat.com/security/cve/CVE-2026-33846)** | important | 2026-05-04 | gnutls: GnuTLS: Denial of Service via heap buffer overflow in DTLS handshake fragment reassembly |
| **[CVE-2026-7598](https://access.redhat.com/security/cve/CVE-2026-7598)** | important | 2026-05-01 | libssh2: integer overflow via large username or password arguments |
| **[CVE-2026-43003](https://access.redhat.com/security/cve/CVE-2026-43003)** | important | 2026-05-01 | ironic-python-agent: OpenStack ironic-python-agent: Arbitrary code execution via malicious image |
| **[CVE-2026-3832](https://access.redhat.com/security/cve/CVE-2026-3832)** | low | 2026-04-30 | gnutls: gnutls: Security bypass allows acceptance of revoked server certificates via crafted OCSP response |
| **[CVE-2026-33845](https://access.redhat.com/security/cve/CVE-2026-33845)** | important | 2026-04-30 | gnutls: GnuTLS: Denial of Service via DTLS zero-length fragment |
| **[CVE-2026-3833](https://access.redhat.com/security/cve/CVE-2026-3833)** | moderate | 2026-04-30 | gnutls: GnuTLS: Policy bypass due to case-sensitive nameConstraints comparison |
| **[CVE-2025-14576](https://access.redhat.com/security/cve/CVE-2025-14576)** | important | 2026-04-30 | qt: Qt SVG: Arbitrary QML/JavaScript code injection via malicious SVG file |
| **[CVE-2026-4873](https://access.redhat.com/security/cve/CVE-2026-4873)** | moderate | 2026-04-29 | curl: curl: Information disclosure due to incorrect TLS connection reuse |
| **[CVE-2026-5773](https://access.redhat.com/security/cve/CVE-2026-5773)** | moderate | 2026-04-29 | curl: libcurl: Wrong file transfer due to incorrect SMB connection reuse |
| **[CVE-2026-6253](https://access.redhat.com/security/cve/CVE-2026-6253)** | moderate | 2026-04-29 | curl: curl: Proxy credential disclosure via redirects to unauthenticated proxies |
| **[CVE-2026-6276](https://access.redhat.com/security/cve/CVE-2026-6276)** | low | 2026-04-29 | curl: libcurl: Information disclosure due to cookie leak when reusing connections with custom Host headers |
| **[CVE-2026-5545](https://access.redhat.com/security/cve/CVE-2026-5545)** | moderate | 2026-04-29 | curl: libcurl: Authentication bypass due to incorrect HTTP Negotiate connection reuse |
| **[CVE-2026-6429](https://access.redhat.com/security/cve/CVE-2026-6429)** | moderate | 2026-04-29 | curl: libcurl: Credential leak via reused proxy connection during HTTP redirects |
| **[CVE-2026-42009](https://access.redhat.com/security/cve/CVE-2026-42009)** | important | 2026-04-29 | gnutls: gnutls: Denial of Service via DTLS packet reordering vulnerability |
| **[CVE-2026-42010](https://access.redhat.com/security/cve/CVE-2026-42010)** | important | 2026-04-29 | gnutls: gnutls: Authentication Bypass via NUL Character in Username |
| **[CVE-2026-42011](https://access.redhat.com/security/cve/CVE-2026-42011)** | moderate | 2026-04-29 | gnutls: gnutls: Security bypass due to incorrect name constraint handling |
| **[CVE-2026-42012](https://access.redhat.com/security/cve/CVE-2026-42012)** | moderate | 2026-04-29 | gnutls: gnutls: Certificate validation bypass due to improper handling of URI and SRV SANs |
| **[CVE-2026-42013](https://access.redhat.com/security/cve/CVE-2026-42013)** | moderate | 2026-04-29 | gnutls: gnutls: Certificate validation bypass due to oversized Subject Alternative Name |
| **[CVE-2026-5260](https://access.redhat.com/security/cve/CVE-2026-5260)** | moderate | 2026-04-29 | gnutls: gnutls: Information disclosure via heap overread in RSA key exchange |
| **[CVE-2026-42014](https://access.redhat.com/security/cve/CVE-2026-42014)** | moderate | 2026-04-29 | gnutls: Fix use-after-free in gnutls_pkcs11_token_set_pin |
| **[CVE-2026-42015](https://access.redhat.com/security/cve/CVE-2026-42015)** | moderate | 2026-04-29 | gnutls: gnutls: Memory corruption due to off-by-one error in PKCS#12 bag handling |
| **[CVE-2026-6238](https://access.redhat.com/security/cve/CVE-2026-6238)** | moderate | 2026-04-28 | glibc: glibc: Application crash or uninitialized memory read via crafted DNS response |
| **[CVE-2026-5435](https://access.redhat.com/security/cve/CVE-2026-5435)** | moderate | 2026-04-28 | glibc: glibc: Out-of-bounds write via TSIG record processing |
| **[CVE-2026-41636](https://access.redhat.com/security/cve/CVE-2026-41636)** | moderate | 2026-04-28 | apache.com/apache/thrift: Apache Thrift: Node.js skip() recursion |
| **[CVE-2026-41607](https://access.redhat.com/security/cve/CVE-2026-41607)** | important | 2026-04-28 | Apache Thrift: apache.com/apache/thrift: Apache Thrift: Out-of-bounds Read vulnerability |
| **[CVE-2026-41606](https://access.redhat.com/security/cve/CVE-2026-41606)** | important | 2026-04-28 | Apache Thrift: Apache Thrift: Denial of Service via uncontrolled recursion |
| **[CVE-2026-41605](https://access.redhat.com/security/cve/CVE-2026-41605)** | important | 2026-04-28 | Apache Thrift: Apache Thrift: Integer Overflow or Wraparound Vulnerability |
| **[CVE-2026-41604](https://access.redhat.com/security/cve/CVE-2026-41604)** | important | 2026-04-28 | Apache Thrift: apache.com/apache/thrift: Apache Thrift: Out-of-bounds Read vulnerability |
| **[CVE-2026-6993](https://access.redhat.com/security/cve/CVE-2026-6993)** | moderate | 2026-04-25 | net/http: golang: github.com/go-kratos/kratos: go-kratos kratos: Information disclosure via unintended HTTP server intermediary |
| **[CVE-2026-41907](https://access.redhat.com/security/cve/CVE-2026-41907)** | moderate | 2026-04-24 | uuid: uuid: Out-of-bounds write vulnerability impacts data integrity and confidentiality |
| **[CVE-2026-42042](https://access.redhat.com/security/cve/CVE-2026-42042)** | moderate | 2026-04-24 | axios: Axios: XSRF token bypass leading to information disclosure |
| **[CVE-2026-42039](https://access.redhat.com/security/cve/CVE-2026-42039)** | important | 2026-04-24 | axios: Node.js: Axios: Denial of Service via unbounded recursion in toFormData with deeply nested request data |
| **[CVE-2026-42036](https://access.redhat.com/security/cve/CVE-2026-42036)** | moderate | 2026-04-24 | axios: Axios: Denial of Service via unbounded stream consumption when 'responseType: 'stream'' is used |
| **[CVE-2026-42034](https://access.redhat.com/security/cve/CVE-2026-42034)** | moderate | 2026-04-24 | axios: Axios: Denial of Service via oversized streamed uploads bypassing body limits |
| **[CVE-2026-42037](https://access.redhat.com/security/cve/CVE-2026-42037)** | moderate | 2026-04-24 | axios: Node.js: Axios: Information disclosure via CRLF injection in multipart Content-Type header |
| **[CVE-2026-42038](https://access.redhat.com/security/cve/CVE-2026-42038)** | moderate | 2026-04-24 | axios: Axios: Information disclosure due to `no_proxy` bypass |
| **[CVE-2026-42041](https://access.redhat.com/security/cve/CVE-2026-42041)** | important | 2026-04-24 | axios: Axios: Authentication bypass due to prototype pollution of HTTP error handling |
| **[CVE-2026-42043](https://access.redhat.com/security/cve/CVE-2026-42043)** | important | 2026-04-24 | axios: Axios: NO_PROXY bypass via crafted URL |
| **[CVE-2026-42044](https://access.redhat.com/security/cve/CVE-2026-42044)** | important | 2026-04-24 | axios: Axios: Invisible JSON Response Tampering via Prototype Pollution Gadget |
| **[CVE-2026-42035](https://access.redhat.com/security/cve/CVE-2026-42035)** | moderate | 2026-04-24 | axios: Axios: Arbitrary HTTP header injection via prototype pollution |
| **[CVE-2026-42033](https://access.redhat.com/security/cve/CVE-2026-42033)** | important | 2026-04-24 | axios: Axios: HTTP Transport Hijacking via Prototype Pollution |
| **[CVE-2026-41305](https://access.redhat.com/security/cve/CVE-2026-41305)** | moderate | 2026-04-24 | postcss: PostCSS: Cross-Site Scripting (XSS) via improper escaping of style closing tags |
| **[CVE-2026-32952](https://access.redhat.com/security/cve/CVE-2026-32952)** | moderate | 2026-04-24 | go-ntlmssp: go-ntlmssp: Denial of Service via malicious NTLM challenge |
| **[CVE-2026-41240](https://access.redhat.com/security/cve/CVE-2026-41240)** | moderate | 2026-04-23 | DOMPurify: DOMPurify: Cross-Site Scripting (XSS) via inconsistent tag sanitization |
| **[CVE-2026-41239](https://access.redhat.com/security/cve/CVE-2026-41239)** | moderate | 2026-04-23 | DOMPurify: Vue 2: DOMPurify: Cross-site scripting due to incomplete sanitization of template expressions |
| **[CVE-2026-41238](https://access.redhat.com/security/cve/CVE-2026-41238)** | moderate | 2026-04-23 | DOMPurify: DOMPurify: Cross-Site Scripting bypass via prototype pollution |
| **[CVE-2026-41988](https://access.redhat.com/security/cve/CVE-2026-41988)** | low | 2026-04-23 | uuid: uuid: Unexpected data writes when using external output buffers with specific UUID versions |
| **[CVE-2026-40923](https://access.redhat.com/security/cve/CVE-2026-40923)** | moderate | 2026-04-21 | github.com/tektoncd/pipeline: Tekton Pipelines: Unauthorized access and information disclosure via path validation bypass |
| **[CVE-2026-40924](https://access.redhat.com/security/cve/CVE-2026-40924)** | moderate | 2026-04-21 | github.com/tektoncd/pipeline: Tekton Pipelines: Denial of Service via large HTTP response body |
| **[CVE-2026-40938](https://access.redhat.com/security/cve/CVE-2026-40938)** | important | 2026-04-21 | github.com/tektoncd/pipeline: Tekton Pipelines: Arbitrary code execution and secret exfiltration via malicious git commands |
| **[CVE-2026-40895](https://access.redhat.com/security/cve/CVE-2026-40895)** | important | 2026-04-21 | follow-redirects: follow-redirects: Information disclosure via cross-domain redirects |
| **[CVE-2026-33812](https://access.redhat.com/security/cve/CVE-2026-33812)** | moderate | 2026-04-21 | golang.org/x/image: golang: golang.org/x/image: Denial of Service due to excessive memory allocation when parsing malicious font files |
| **[CVE-2026-33813](https://access.redhat.com/security/cve/CVE-2026-33813)** | moderate | 2026-04-21 | golang.org/x/image: golang: golang.org/x/image: Denial of Service via malformed WEBP image parsing |
| **[CVE-2026-40161](https://access.redhat.com/security/cve/CVE-2026-40161)** | moderate | 2026-04-21 | github.com/tektoncd/pipeline: Tekton Pipelines: Information disclosure of Git API token via user-controlled serverURL |
| **[CVE-2026-25542](https://access.redhat.com/security/cve/CVE-2026-25542)** | moderate | 2026-04-21 | github.com/tektoncd/pipeline: Tekton Pipelines: Security bypass due to regular expression matching flaw |
| **[CVE-2026-6383](https://access.redhat.com/security/cve/CVE-2026-6383)** | moderate | 2026-04-15 | kubevirt: KubeVirt: Unauthorized subresource access due to improper RBAC evaluation |
| **[CVE-2026-35469](https://access.redhat.com/security/cve/CVE-2026-35469)** | important | 2026-04-13 | Kubelet: CRI-O: kube-apiserver: Kubelet, CRI-O, kube-apiserver: Denial of Service via SPDY streaming code |
| **[CVE-2026-40175](https://access.redhat.com/security/cve/CVE-2026-40175)** | important | 2026-04-10 | axios: Axios: Remote Code Execution via Prototype Pollution escalation |
| **[CVE-2025-62718](https://access.redhat.com/security/cve/CVE-2025-62718)** | important | 2026-04-09 | axios: Axios: Server-Side Request Forgery and proxy bypass due to improper hostname normalization |
| **[CVE-2026-39865](https://access.redhat.com/security/cve/CVE-2026-39865)** | moderate | 2026-04-08 | axios: Axios: Denial of Service via HTTP/2 session cleanup logic state corruption |
| **[CVE-2026-32281](https://access.redhat.com/security/cve/CVE-2026-32281)** | moderate | 2026-04-08 | crypto/x509: golang: Go crypto/x509: Denial of Service via inefficient certificate chain validation |
| **[CVE-2026-32280](https://access.redhat.com/security/cve/CVE-2026-32280)** | important | 2026-04-08 | crypto/x509: crypto/tls: golang: Go: Denial of Service vulnerability in certificate chain building |
| **[CVE-2026-32288](https://access.redhat.com/security/cve/CVE-2026-32288)** | moderate | 2026-04-08 | archive/tar: golang: Go's archive/tar package: Denial of Service via maliciously-crafted archive |
| **[CVE-2026-32283](https://access.redhat.com/security/cve/CVE-2026-32283)** | important | 2026-04-08 | crypto/tls: golang: Go crypto/tls: Denial of Service via multiple TLS 1.3 key update messages |
| **[CVE-2026-27140](https://access.redhat.com/security/cve/CVE-2026-27140)** | important | 2026-04-08 | cmd/go: golang: Go (golang) and cmd/go: Arbitrary Code Execution via malicious SWIG file names |
| **[CVE-2026-27143](https://access.redhat.com/security/cve/CVE-2026-27143)** | moderate | 2026-04-08 | golang: cmd/compile: possible memory corruption after bound check elimination |
| **[CVE-2026-32289](https://access.redhat.com/security/cve/CVE-2026-32289)** | moderate | 2026-04-08 | html/template: golang: html/template: Cross-Site Scripting (XSS) via improper context and brace depth tracking in JS template literals |
| **[CVE-2026-33810](https://access.redhat.com/security/cve/CVE-2026-33810)** | important | 2026-04-08 | crypto/x509: golang: Go crypto/x509: Certificate validation bypass due to incorrect DNS constraint application |
| **[CVE-2026-27144](https://access.redhat.com/security/cve/CVE-2026-27144)** | moderate | 2026-04-08 | golang: cmd/compile: no-op interface conversion bypasses overlap checking |
| **[CVE-2026-32282](https://access.redhat.com/security/cve/CVE-2026-32282)** | moderate | 2026-04-08 | golang: internal/syscall/unix: Root.Chmod can follow symlinks out of the root |
| **[CVE-2026-34986](https://access.redhat.com/security/cve/CVE-2026-34986)** | important | 2026-04-06 | github.com/go-jose/go-jose/v3: github.com/go-jose/go-jose/v4: Go JOSE: Denial of Service via crafted JSON Web Encryption (JWE) object |
| **[CVE-2026-4800](https://access.redhat.com/security/cve/CVE-2026-4800)** | important | 2026-03-31 | lodash: lodash: Arbitrary code execution via untrusted input in template imports |
| **[CVE-2026-2950](https://access.redhat.com/security/cve/CVE-2026-2950)** | moderate | 2026-03-31 | lodash: Lodash: Prototype pollution allows deletion of built-in prototype properties via array path bypass |
| **[CVE-2026-33762](https://access.redhat.com/security/cve/CVE-2026-33762)** | low | 2026-03-31 | github.com/go-git/go-git/v5: go-git: Denial of Service via crafted Git index file |
| **[CVE-2026-34165](https://access.redhat.com/security/cve/CVE-2026-34165)** | moderate | 2026-03-31 | github.com/go-git/go-git/v5: go-git: Denial of Service via crafted .idx file |
| **[CVE-2026-34043](https://access.redhat.com/security/cve/CVE-2026-34043)** | moderate | 2026-03-31 | serialize-javascript: serialize-javascript: Denial of Service via specially crafted array-like object serialization |
| **[CVE-2026-33997](https://access.redhat.com/security/cve/CVE-2026-33997)** | important | 2026-03-31 | moby: docker: github.com/moby/moby: Moby: Privilege validation bypass during plugin installation |
| **[CVE-2026-34040](https://access.redhat.com/security/cve/CVE-2026-34040)** | moderate | 2026-03-31 | Moby: Moby: Authorization bypass vulnerability |
| **[CVE-2026-33750](https://access.redhat.com/security/cve/CVE-2026-33750)** | moderate | 2026-03-27 | brace-expansion: brace-expansion: Denial of Service via zero step value in brace pattern |
| **[CVE-2026-33532](https://access.redhat.com/security/cve/CVE-2026-33532)** | moderate | 2026-03-26 | yaml: yaml: Denial of Service via deeply nested YAML document parsing |
| **[CVE-2026-4923](https://access.redhat.com/security/cve/CVE-2026-4923)** | moderate | 2026-03-26 | path-to-regexp: path-to-regexp: Denial of Service via specially crafted paths with multiple wildcards |
| **[CVE-2026-4926](https://access.redhat.com/security/cve/CVE-2026-4926)** | important | 2026-03-26 | path-to-regexp: path-to-regexp: Denial of Service via crafted regular expressions |
| **[CVE-2026-4867](https://access.redhat.com/security/cve/CVE-2026-4867)** | moderate | 2026-03-26 | path-to-regexp: path-to-regexp: Denial of Service via catastrophic backtracking from malformed URL parameters |
| **[CVE-2026-33809](https://access.redhat.com/security/cve/CVE-2026-33809)** | moderate | 2026-03-25 | golang: golang.org/x/image/tiff: golang.org/x/image/tiff: Denial of Service via maliciously crafted TIFF file |
| **[CVE-2026-33349](https://access.redhat.com/security/cve/CVE-2026-33349)** | moderate | 2026-03-24 | fast-xml-parser: fast-xml-parser: Denial of Service via unbounded entity expansion due to incorrect configuration limit handling |
| **[CVE-2026-33211](https://access.redhat.com/security/cve/CVE-2026-33211)** | important | 2026-03-23 | Tekton Pipelines: github.com/tektoncd/pipeline: Tekton Pipelines: Information disclosure via path traversal in git resolver |
| **[CVE-2026-33186](https://access.redhat.com/security/cve/CVE-2026-33186)** | important | 2026-03-20 | google.golang.org/grpc/grpc-go: google.golang.org/grpc/authz: gRPC-Go: Authorization bypass due to improper HTTP/2 path validation |
| **[CVE-2026-33022](https://access.redhat.com/security/cve/CVE-2026-33022)** | moderate | 2026-03-20 | github.com/tektoncd/pipeline: Tekton Pipelines: Denial of Service via long resolver names |
| **[CVE-2026-33036](https://access.redhat.com/security/cve/CVE-2026-33036)** | moderate | 2026-03-20 | fast-xml-parser: fast-xml-parser: Denial of Service via XML entity expansion bypass |
| **[CVE-2026-32274](https://access.redhat.com/security/cve/CVE-2026-32274)** | important | 2026-03-12 | black: Black: Arbitrary file writes from unsanitized user input in cache file name |
| **[CVE-2026-27139](https://access.redhat.com/security/cve/CVE-2026-27139)** | low | 2026-03-06 | os: FileInfo can escape from a Root in golang os module |
| **[CVE-2026-27138](https://access.redhat.com/security/cve/CVE-2026-27138)** | low | 2026-03-06 | crypto/x509: Panic in name constraint checking for malformed certificates in crypto/x509 |
| **[CVE-2026-27142](https://access.redhat.com/security/cve/CVE-2026-27142)** | moderate | 2026-03-06 | html/template: URLs in meta content attribute actions are not escaped in html/template |
| **[CVE-2026-25679](https://access.redhat.com/security/cve/CVE-2026-25679)** | important | 2026-03-06 | net/url: Incorrect parsing of IPv6 host literals in net/url |
| **[CVE-2026-27137](https://access.redhat.com/security/cve/CVE-2026-27137)** | important | 2026-03-06 | crypto/x509: Incorrect enforcement of email constraints in crypto/x509 |
| **[CVE-2026-29063](https://access.redhat.com/security/cve/CVE-2026-29063)** | important | 2026-03-06 | immutable-js: Immutable.js: Arbitrary code execution via Prototype Pollution |
| **[CVE-2025-15558](https://access.redhat.com/security/cve/CVE-2025-15558)** | important | 2026-03-04 | docker/cli: Docker CLI for Windows: Privilege escalation via malicious plugin binaries |
| **[CVE-2026-0540](https://access.redhat.com/security/cve/CVE-2026-0540)** | moderate | 2026-03-03 | DOMPurify: DOMPurify: Cross-site scripting vulnerability |
| **[CVE-2025-15599](https://access.redhat.com/security/cve/CVE-2025-15599)** | moderate | 2026-03-03 | DOMPurify: DOMPurify: Cross-site scripting |
| **[CVE-2026-27141](https://access.redhat.com/security/cve/CVE-2026-27141)** | moderate | 2026-02-26 | golang.org/x/net/http2: golang.org/x/net/http2: Denial of Service due to malformed HTTP/2 frames |
| **[CVE-2026-27942](https://access.redhat.com/security/cve/CVE-2026-27942)** | moderate | 2026-02-26 | fast-xml-parser: fast-xml-parser: Stack overflow leads to Denial of Service |
| **[CVE-2026-25896](https://access.redhat.com/security/cve/CVE-2026-25896)** | important | 2026-02-20 | fast-xml-parser: fast-xml-parser: Cross-Site Scripting (XSS) due to improper DOCTYPE entity handling |
| **[CVE-2026-26963](https://access.redhat.com/security/cve/CVE-2026-26963)** | moderate | 2026-02-19 | cilium: Cilium: Information disclosure via incorrect traffic permitting with specific network configurations |
| **[CVE-2026-26278](https://access.redhat.com/security/cve/CVE-2026-26278)** | important | 2026-02-19 | fast-xml-parser: fast-xml-parser: Denial of Service via unlimited XML entity expansion |
| **[CVE-2026-25934](https://access.redhat.com/security/cve/CVE-2026-25934)** | moderate | 2026-02-09 | go-git/go-git: go-git: Data integrity issue due to improper verification of pack and index files |
| **[CVE-2026-25639](https://access.redhat.com/security/cve/CVE-2026-25639)** | important | 2026-02-09 | axios: Axios affected by Denial of Service via __proto__ Key in mergeConfig |
| **[CVE-2025-47911](https://access.redhat.com/security/cve/CVE-2025-47911)** | moderate | 2026-02-05 | golang.org/x/net/html: Quadratic parsing complexity in golang.org/x/net/html |
| **[CVE-2025-68121](https://access.redhat.com/security/cve/CVE-2025-68121)** | moderate | 2026-02-05 | crypto/tls: crypto/tls: Incorrect certificate validation during TLS session resumption |
| **[CVE-2025-61732](https://access.redhat.com/security/cve/CVE-2025-61732)** | important | 2026-02-05 | cmd/cgo: Go cgo: Code smuggling due to comment parsing discrepancy |
| **[CVE-2025-22873](https://access.redhat.com/security/cve/CVE-2025-22873)** | moderate | 2026-02-04 | os: os: Information disclosure via path traversal using specially crafted filenames |
| **[CVE-2026-25128](https://access.redhat.com/security/cve/CVE-2026-25128)** | moderate | 2026-01-30 | fast-xml-parser: fast-xml-parser has RangeError DoS Numeric Entities Bug |
| **[CVE-2025-61728](https://access.redhat.com/security/cve/CVE-2025-61728)** | moderate | 2026-01-28 | golang: archive/zip: Excessive CPU consumption when building archive index in archive/zip |
| **[CVE-2025-61726](https://access.redhat.com/security/cve/CVE-2025-61726)** | important | 2026-01-28 | golang: net/url: Memory exhaustion in query parameter parsing in net/url |
| **[CVE-2025-61730](https://access.redhat.com/security/cve/CVE-2025-61730)** | moderate | 2026-01-28 | crypto/tls: Handshake messages may be processed at the incorrect encryption level in crypto/tls |
| **[CVE-2025-61731](https://access.redhat.com/security/cve/CVE-2025-61731)** | important | 2026-01-28 | cmd/go: cmd/go: Arbitrary file write via malicious pkg-config directive |
| **[CVE-2026-24137](https://access.redhat.com/security/cve/CVE-2026-24137)** | moderate | 2026-01-23 | github.com/sigstore/sigstore: sigstore legacy TUF client allows for arbitrary file writes with target cache path traversal |
| **[CVE-2025-13465](https://access.redhat.com/security/cve/CVE-2025-13465)** | important | 2026-01-21 | lodash: prototype pollution in _.unset and _.omit functions |
