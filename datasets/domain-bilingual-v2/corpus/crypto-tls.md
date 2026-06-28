---
title: The TLS handshake
language: en
source: openai-codex-synthetic
---

# The TLS handshake

## Purpose in HTTPS

The TLS handshake is the protocol step that lets a client and server agree on fresh session keys and lets the client authenticate that it is talking to the intended server. In HTTPS, this happens before HTTP requests are sent, for example when a browser connects to `https://www.example.com`.

TLS does not replace ciphers, hashes, signatures, certificates, or key exchange. Instead, it coordinates them. Modern TLS 1.3, standardized in RFC 8446, combines these primitives into a short sequence of messages that establishes an encrypted channel with server identity checking.

## Main handshake flow

A typical TLS 1.3 handshake begins with a **ClientHello**. The client sends supported protocol versions, cipher suites, random data, extensions such as SNI, and key-share information.

The server replies with a **ServerHello**, selecting the TLS version, cipher suite, and matching key-share parameters. From the exchanged values, both sides derive temporary session secrets for this connection. These secrets are then expanded into traffic keys used to protect later handshake and application records.

Next, the server sends its **Certificate** message. This usually contains an X.509 certificate chain linking the server name, such as `www.example.com`, to a public key trusted through a certificate authority such as DigiCert or Let’s Encrypt. The client validates the chain, the hostname, expiration dates, and policy requirements.

The server then sends **CertificateVerify**, proving possession of the private key corresponding to the certificate. Finally, both sides send **Finished** messages, which confirm that the same handshake transcript and derived secrets were used.

## What the handshake guarantees

The TLS handshake provides two central results:

1. **Session key negotiation:** client and server end with shared traffic keys that were not sent directly over the network.
2. **Server authentication:** the client gains evidence that the server controls the private key for a certificate valid for the requested name.

After the handshake, application data such as HTTP headers, cookies, and request bodies is protected using the negotiated record-layer algorithms. Session resumption and PSK modes can shorten later connections, but the core idea remains the same: TLS is the protocol that combines cryptographic primitives to authenticate the server and establish keys for a secure session.
