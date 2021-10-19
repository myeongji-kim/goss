import json
import config.kr_config as kr
import config.jp_config as jp
import lib.create_goss_intance as goss_lib
from requests.packages.urllib3.util import Retry
from requests.adapters import HTTPAdapter
from requests import Session


class ConfigIaaSInstance:
    def __init__(self, region):
        self.data = {
            "addSecurityGroup": {
                "name": "goss-ssh"
            }
        }
        self.region = region

    # 토큰 생성 후 헤더 리턴
    def _get_new_token(self):
        headers = {'Content-Type': 'application/json'}
        data = {
            "auth": {
                "tenantId": globals()[self.region].config['tenantId'],
                "passwordCredentials": {
                    "username": "admin",
                    "password": "admin"
                }
            }
        }
        session = Session()
        session.mount(globals()[self.region].config['token_url'],
                      HTTPAdapter(max_retries=Retry(total=20, method_whitelist=frozenset(['GET', 'POST']))))
        response = session.post(globals()[self.region].config['token_url'],
                                data=json.dumps(data),
                                headers=headers).json()['access']['token']['id']
        return {'X-Auth-Token': response,
                'Content-Type': 'application/json'}

    def addsecuritygroup(self, public_ip, _):
        print(f"IaaS - add security group to {public_ip}")
        cri = goss_lib.CreategossInstance(self.region)
        # instance_id, public_ip = cri.inquiryInstance()
        instance_dict = cri.inquiryInstance()

        try:
            for instance_id, ip in instance_dict.items():
                if ip == public_ip:
                    print('IaaS Instance Id: ', instance_id, 'FIP: ', ip)
                    session = Session()
                    session.mount(globals()[self.region].config['add_security_url'] + instance_id + '/action',
                                  HTTPAdapter(max_retries=Retry(total=100, method_whitelist=frozenset(['GET', 'POST']))))
                    response = session.post(globals()[self.region].config['add_security_url'] + instance_id + '/action',
                                            headers=self._get_new_token(), json=self.data)
                    print(response)
                else:
                    continue
        except Exception as e:
            print("add security group is failed. check error messages.")
            print(e)
