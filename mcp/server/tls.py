"""
TLS 证书管理 — 自签名证书生成与 SSL Context
"""

import logging
import os
import ssl
from pathlib import Path

logger = logging.getLogger("orchestra.mcp.tls")


class TLSManager:
    """TLS 证书管理器"""

    def __init__(self, cert_dir: str = "./data/certs"):
        self.cert_dir = Path(cert_dir)
        self.cert_path = self.cert_dir / "cert.pem"
        self.key_path = self.cert_dir / "key.pem"

    def ensure_certificates(self) -> tuple[str, str]:
        """
        确保证书存在，如果不存在则生成自签名证书

        Returns:
            (cert_path, key_path)
        """
        if self.cert_path.exists() and self.key_path.exists():
            logger.debug(f"TLS 证书已存在: {self.cert_path}")
            return str(self.cert_path), str(self.key_path)

        self.cert_dir.mkdir(parents=True, exist_ok=True)
        self._generate_self_signed_cert()
        logger.info(f"已生成自签名 TLS 证书: {self.cert_path}")
        return str(self.cert_path), str(self.key_path)

    def _generate_self_signed_cert(self) -> None:
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            import datetime
        except ImportError:
            self._generate_with_openssl()
            return

        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Beijing"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Beijing"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Orchestra"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName([
                    x509.DNSName("localhost"),
                    x509.IPAddress(__import__("ipaddress").IPv4Address("127.0.0.1")),
                ]),
                critical=False,
            )
            .sign(key, hashes.SHA256())
        )

        with open(self.key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ))

        with open(self.cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

    def _generate_with_openssl(self) -> None:
        import subprocess

        cmd = [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(self.key_path),
            "-out", str(self.cert_path),
            "-days", "365",
            "-nodes",
            "-subj", "/CN=localhost/O=Orchestra/C=CN",
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            raise RuntimeError(
                "无法生成 TLS 证书：请安装 cryptography 库或 openssl 命令"
            ) from e

    def get_ssl_context(self) -> ssl.SSLContext:
        """返回配置好的 SSLContext"""
        cert_path, key_path = self.ensure_certificates()

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
        ctx.set_ciphers("ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256")
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        return ctx
