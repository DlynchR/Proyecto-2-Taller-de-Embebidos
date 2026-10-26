SUMMARY = "Red de la imagen EdgeAI (systemd-networkd, Wi-Fi, mDNS)"
DESCRIPTION = "Ethernet con DHCP y respaldo link-local, Wi-Fi opcional con wpa_supplicant y \
publicación del nombre edgeai.local por mDNS con systemd-resolved."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "\
    file://10-eth0.network \
    file://20-wlan0.network \
    file://edgeai-mdns.conf \
"
S = "${UNPACKDIR}"

inherit allarch

# Defínalas en edgeai-secrets.conf. Sin SSID, el Wi-Fi queda apagado.
EDGEAI_WIFI_SSID ??= ""
EDGEAI_WIFI_PSK ??= ""
EDGEAI_WIFI_COUNTRY ??= "CR"
EDGEAI_WIFI_SSID:qemuarm64 = ""
EDGEAI_WIFI_PSK:qemuarm64 = ""

python do_install() {
    import hashlib
    import re
    import shutil
    from pathlib import Path

    config = Path(d.getVar('D') + d.getVar('sysconfdir'))
    source = Path(d.getVar('UNPACKDIR'))
    for filename, directory in (
        ('10-eth0.network', 'systemd/network'),
        ('20-wlan0.network', 'systemd/network'),
        ('edgeai-mdns.conf', 'systemd/resolved.conf.d'),
    ):
        target = config / directory / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / filename, target)
        target.chmod(0o644)

    ssid = d.getVar('EDGEAI_WIFI_SSID') or ''
    if ssid:
        password = d.getVar('EDGEAI_WIFI_PSK') or ''
        country = d.getVar('EDGEAI_WIFI_COUNTRY')
        if not 1 <= len(ssid.encode('utf-8')) <= 32:
            bb.fatal('El SSID debe ocupar entre 1 y 32 bytes')
        if not re.fullmatch('[A-Z]{2}', country):
            bb.fatal('EDGEAI_WIFI_COUNTRY debe ser un codigo de dos letras')
        if re.fullmatch('[a-fA-F0-9]{64}', password):
            psk = password.lower()
        else:
            if not 8 <= len(password.encode('utf-8')) <= 63:
                bb.fatal('La clave WPA debe ocupar entre 8 y 63 bytes')
            psk = hashlib.pbkdf2_hmac('sha1', password.encode('utf-8'), ssid.encode('utf-8'), 4096, dklen=32).hex()
        target = config / 'wpa_supplicant/wpa_supplicant-wlan0.conf'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('ctrl_interface=/run/wpa_supplicant\nupdate_config=1\n'
                          f'country={country}\n\nnetwork={{\n'
                          f'    ssid={ssid.encode("utf-8").hex()}\n    psk={psk}\n}}\n')
        target.chmod(0o600)
        service = config / 'systemd/system/multi-user.target.wants/wpa_supplicant@wlan0.service'
        service.parent.mkdir(parents=True, exist_ok=True)
        service.symlink_to(d.getVar('systemd_system_unitdir') + '/wpa_supplicant@.service')
}

RDEPENDS:${PN} = "wpa-supplicant"
