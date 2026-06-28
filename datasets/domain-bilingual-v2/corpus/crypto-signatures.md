---
title: Digital signatures
language: en
source: openai-codex-synthetic
---

# Digital signatures

## Purpose and security property

A digital signature is a public-key primitive used to prove that a particular private key approved an exact message. In common signing formats—such as CMS/PKCS #7 `SignedData` used by S/MIME, OpenPGP signatures, and PDF Advanced Electronic Signatures—a signer first obtains a message digest of the bytes to be authorized and then applies a signature algorithm with the private key. The result is a compact signature value stored with or beside the document.

The security goal is authenticity and integrity: if the document changes by one byte, recomputing the digest makes verification fail. A signature can also support non-repudiation: when a private key is assigned to Alice, kept under her exclusive control, and certified or logged, a valid signature is evidence that Alice authorized the signed content. In practice, non-repudiation also depends on key custody, timestamps, revocation status, policy, and audit records; mathematics alone does not prove human intent.

## Signing a digest with the private key

A typical signing workflow is:

1. Serialize or canonicalize the exact content to be signed, including context such as `invoice-v1`, a document identifier, or signing time if required.
2. Produce a fixed-length digest of that content, for example a SHA-256 digest.
3. Use the private signing key with an algorithm such as RSA-PSS, ECDSA over NIST P-256, or Ed25519ph to generate a signature over the digest or algorithm-defined transcript.
4. Publish the message, signature, algorithm identifiers, and the signer’s public-key certificate or fingerprint.

The private key never leaves the signer’s control, often remaining inside a YubiKey, smart card, or FIPS-validated hardware security module. It is not accurate to describe modern signing as simply “encrypting with the private key”; real schemes use padding, domain separation, nonce rules, and algorithm-specific checks to prevent forgery.

## Verification with the public key

A verifier obtains the signer’s authentic public key, recomputes the digest from the received bytes, and checks the signature according to the declared algorithm. Verification returns valid or invalid; it does not recover hidden content or provide secrecy. A valid result means the holder of the matching private key signed that exact digest, so later modification, substitution, or accidental corruption is detectable.
