# -*- coding: utf-8 -*-

import lib.create_goss_intance as cri
import lib.config_iaas_instance as cii
from re import search, compile
import paramiko
import time


class TestGoss:
    def precondition_for_goss(self, engine, region):
        cri_goss = cri.CreategossInstance(region)
        cii_iaas = cii.ConfigIaaSInstance(region)

        goss_name = cri_goss.creategoss(engine)
        goss, gossid = cri_goss.inquirygossinstance(goss_name)
        cri_goss.check_goss_stable(gossid)
        public_ip, _ = cri_goss.inquirygossinstanceId(gossid)

        cii_iaas.addsecuritygroup(public_ip, _)
        return self.sshHandler(public_ip, region)

    def test_V5633(self, region):
        returned_string = self.precondition_for_goss('5633', region=region)
        assert "Failed: 0" in returned_string

    def test_V5715(self, region):
        returned_string = self.precondition_for_goss('5715', region=region)
        assert "Failed: 0" in returned_string

    def test_V5719(self, region):
        returned_string = self.precondition_for_goss('5719', region=region)
        assert "Failed: 0" in returned_string

    def test_V5726(self, region):
        returned_string = self.precondition_for_goss('5726', region=region)
        assert "Failed: 0" in returned_string

    def test_V8018(self, region):
        returned_string = self.precondition_for_goss('8018', region=region)
        assert "Failed: 0" in returned_string

    @staticmethod
    def sshHandler(pip, region):
        pem_dir = ('pem/goss-jp.pem' if region == "jp" else 'pem/goss.pem').__str__()
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_key = paramiko.RSAKey.from_private_key_file(pem_dir)
        print('ssh connected to: ', pip)

        connected = False
        while not connected:
            try:
                ssh.connect(pip, pkey=ssh_key, username='centos', timeout=600, banner_timeout=600, auth_timeout=600)
                connected = True
            except TimeoutError as e:
                time.sleep(5)

        cmd_list = [
            "curl -L -H \"Authorization: token 1111111111111111111111111111111111111111\" \
            https://XXXXXXXX/repos/goss-test/tarball/ | tar xz --wildcards \"*/goss/goss/*\" --strip-components=2",
            f"cd goss && ./check_goss.sh {region}_region"
        ]

        time.sleep(900)  # for ntp server sync

        for cmd in cmd_list:
            print('command: ', cmd)
            _, stdout, stderr = ssh.exec_command(cmd, get_pty=True, timeout=600)  # next command를 위한 timeout 설정

            # ANSI Code Escape
            ansi_escape = compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            for line in stdout.readlines():
                txt = ansi_escape.sub('', line)
                print(txt.strip())

                if search('Failed: ', txt):  # Failed: 문구가 있으면 해당 문구만 리턴
                    if search('Failed: [1-9].*', txt):  # Failed 건수가 1건이라도 존재하는 경우
                        _, stdout, _ = ssh.exec_command("sudo cat /var/log/messages", get_pty=True)
                        print("Please check below log (/var/log/messages).")
                    for catlog in stdout.readlines():
                        print(f'{catlog}', end='')
                else:
                    continue
                return txt.strip(" ")

        ssh.close()
