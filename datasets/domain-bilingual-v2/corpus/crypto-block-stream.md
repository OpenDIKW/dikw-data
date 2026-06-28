---
title: Block vs stream ciphers
language: en
source: openai-codex-synthetic
---

# Block vs stream ciphers

Block ciphers and stream ciphers are symmetric confidentiality primitives, but they package encryption differently. The practical choice affects padding, nonce handling, performance, error behavior, and how safely software can encrypt records, files, or network packets.

## Block ciphers and modes

A block cipher is a keyed permutation on fixed-size blocks. AES, for example, operates on 128-bit blocks; it does not by itself define how to encrypt a message of arbitrary length. A mode of operation supplies that missing structure.

Common modes make different tradeoffs:

- **ECB** encrypts each block independently and is unsafe for most data because equal plaintext blocks produce equal ciphertext blocks.
- **CBC** chains blocks using an initialization vector and requires padding for non-multiple block lengths; decryption errors can affect neighboring blocks.
- **CTR** encrypts counters to create a keystream, making a block cipher behave much like a stream cipher; it needs a unique nonce/counter combination.
- **GCM** combines counter-style encryption with an authentication tag and is widely used when both confidentiality and tamper detection are required.

Block-cipher modes are often a good fit for standardized hardware support, bulk file encryption, and systems that already rely on mature AES implementations. Their main complexity is that the mode rules matter as much as the underlying cipher.

## Stream ciphers

A stream cipher generates a pseudorandom keystream from a secret key plus a nonce or initialization value, then XORs that keystream with plaintext. Encryption and decryption are the same XOR operation. ChaCha20 and Salsa20 are modern examples; RC4 is a historical example that should not be used in new designs.

Stream ciphers naturally handle data of any length, including single bytes, without padding. They are useful for low-latency communication, software-only environments, and packet formats where buffering full blocks would be inconvenient. Many designs use counters internally, allowing efficient seeking or parallel generation.

## Tradeoffs and safety rules

The most important shared rule is uniqueness: never reuse the same keystream. Reusing a stream-cipher key/nonce pair, or reusing a CTR-mode counter sequence, exposes the XOR of the plaintexts and can reveal both messages.

Block ciphers provide a compact, well-analyzed core but require a correct mode. Stream ciphers provide a direct keystream interface but place strict responsibility on nonce management. In practice, use vetted constructions such as AES-GCM or ChaCha20-Poly1305 rather than assembling raw primitives manually.
