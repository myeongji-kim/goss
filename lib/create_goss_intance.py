# -*- coding: utf-8 -*-

import json
import os
import random
import string
import config.kr_config as kr
import config.jp_config as jp
import requests
import time
from datetime import timedelta, datetime
from requests.packages.urllib3.util import Retry
from requests.adapters import HTTPAdapter
from requests import Session

EXCLUDE_goss = ['goss-default', 'default', 'nogateway']


class CreategossInstance:
    def __init__(self, region):
        self.headers = {
            "Content-Type": "application/json",
            "charset": "UTF-8",
            "goss-admin": "goss-admin"
        }
        self.exclude_goss = ['goss-default', 'default', 'nogateway']
        self.region = region

    # 인스턴스명 생성 (ex. goss_V5633_xSQ12g)
    @staticmethod
    def _createInstanceName(filename):
        rand_string = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(6))
        prefix = "goss_V"
        return prefix + filename + "_" + rand_string

    # 토큰 생성 후 헤더 리턴
    def _get_new_token(self):
        headers = {'Content-Type': 'application/json'}
        data = {
            "auth": {
                "tenantId": globals()[self.region].config['tenantId'],
                "passwordCredentials": {
                    "username": "goss-admin",
                    "password": "goss-admin"
                }
            }
        }
        response = requests.post(globals()[self.region].config['token_url'],
                                 data=json.dumps(data),
                                 headers=headers).json()['access']['token']['id']
        return {'X-Auth-Token': response}

    def inquirygossinstanceId(self, instanceid):
        # iframe url로 인스턴스별 endpoint 접근하기
        response = requests.get(globals()[self.region].config['inquiry_goss_iframe_url'] + instanceid,
                                headers=globals()[self.region].config['headers'], ).json()

        # 0: PUBLIC, 1: PRIVATE
        public_endpoint = response['instance']['endpoints'][0]['ipAddress']
        private_endpoint = response['instance']['endpoints'][1]['ipAddress']  # no-gateway일 때 찾기 위한 private ip
        # 향후 public ip가 없는 경우를 대비해 Private_endpoint도 출력받는다. 이를 통해 IaaS 인스턴스의 IP를 조회하려는 용도.
        print(f'public ip: {public_endpoint}, private ip:{private_endpoint}')
        return public_endpoint, private_endpoint

    def inquirygossinstance(self, instance):
        # 1단계, goss 인스턴스 조회를 먼저 진행하고, 그 안에서 매칭되는 name에 따라 return...
        response = requests.get(globals()[self.region].config['goss_url'],
                                headers=globals()[self.region].config['headers'], ).json()

        for goss in response['instances']:
            if goss['instanceName'] == instance:
                print("matched: ", goss['instanceName'], goss['instanceId'], "\n")
                return goss['instanceName'], goss['instanceId']
            else:
                continue

    # 인스턴스 및 인스턴스의 FIP 리스트를 리턴
    def inquiryInstance(self):
        session = Session()
        session.mount(globals()[self.region].config['inquiry_iaas_instance_url'],
                      HTTPAdapter(max_retries=Retry(total=20, method_whitelist=frozenset(['GET', 'POST']))))

        response = session.get(globals()[self.region].config['inquiry_iaas_instance_url'],
                               headers=self._get_new_token()).json()
        instance_dict = {}

        # floating ip address만 찾아 리턴
        try:
            for instance in response['servers']:
                default_network = instance['addresses']['Default Network']
                instance_ids = instance['id']

                instance_ip = next((addr['addr'] for addr in default_network if addr['OS-EXT-IPS:type'] == "floating"),
                                   None)
                instance_dict[instance_ids] = instance_ip
        except KeyError as k:
            print("Dict key is not contained. Please check the response as below.")
            print(json.dumps(response, indent=4, sort_keys=True))
        return instance_dict

    # 인스턴스 생성
    def creategoss(self, goss_engine):
        # 각 engine 별 생성가능한 json 파일을 읽어들임
        # testdata_dir = os.path.abspath('..') + "/testdata/"
        testdata_dir = os.getcwd() + "/testdata/"

        for file in os.listdir(testdata_dir):

            if goss_engine in file:
                sql_engine = file.strip('.json').split("_")[1]
                full_dir = testdata_dir + file

                # json 파일 내의 기본 인스턴스명을 생성한 명칭으로 변경하여 다시 json 파일로 저장 (ex. "goss_V5719_Sxd12A")
                # 해당 json file을 body로 두고 생성하도록 http request 전송
                # flavor, az 랜덤 선택 (flavor는 cpu core 4개 이하만 선택)
                with open(full_dir, "r+", encoding='utf-8') as fp:
                    json_data = json.load(fp)
                    json_data['instanceName'] = self._createInstanceName(sql_engine)
                    json_data['userSubnetId'] = globals()[self.region].config["userSubnetId"]
                    json_data['instance_id'] = random.choice(globals()[self.region].config[f"{self.region}_flavor_list"])
                    fp.seek(0)
                    fp.write(json.dumps(json_data))
                    fp.truncate()
                    response = requests.post(globals()[self.region].config["goss_url"],
                                             headers=globals()[self.region].config["headers"],
                                             json=json_data).json()
                    print(response)

                    # config가 다르거나 값에 문제가 있는경우 invalid response code가 6602이고 SUCCESS가 아닌 invalid reason 출력해준다.
                    # valid fail 되는 경우 default config를 따라가도록 추가, 별 문제 없으면 다음 스텝
                    if response['header']['resultCode'] != 0:
                        print("Cannot create instance. You can check your status.", response['header']['resultMessage'])
                return json_data['instanceName']

    # 생성한 인스턴스들의 stable 상태를 판단하며 30분간 대기하다 문제 발생하면 Exception 발생
    def waitForStable(self, instanceId):
        while True:
            try:
                # add delay slightly to http get
                time.sleep(3)
                session = Session()
                session.mount(globals()[self.region].config["inquiry_goss_iframe_url"] + instanceId,
                              HTTPAdapter(max_retries=Retry(total=20, method_whitelist=frozenset(['GET', 'POST']))))

                response = session.get(
                    globals()[self.region].config["inquiry_goss_iframe_url"] + instanceId + "/metadata",
                    headers=globals()[self.region].config["headers"], ).json()

                if response['header']['resultCode'] == 0:
                    return response['instance']['instanceStatus'] == "STABLE" and \
                           response['instance']['progressStatus'] == "NONE"
                if response['instance']['instanceStatus'] == "FAIL_TO_CREATE":
                    print("Create instance is failed. check message as below. \n", response)
                    break
                elif response['instance']['instanceStatus'] == "FAIL_TO_CONNECT":
                    print("Create. check message as below. \n", response)
                    logs = session.get(
                        globals()[self.region].config["inquiry_goss_iframe_url"] + instanceId + "/logs?logFileName=error.log",
                        headers=globals()[self.region].config["headers"], ).json()
                    print(logs['message'])
                else:  # 그 외 RequestBody 이슈인 경우도 RuntimeError 발생
                    print("http request is failed. \n", response)
                    raise RuntimeError
            except Exception as te:
                print("Create goss instances are failed. \n", te)

    def check_goss_stable(self, goss_instance_id):
        endtime = datetime.utcnow() + timedelta(seconds=2400)
        while not self.waitForStable(goss_instance_id):
            if datetime.utcnow() > endtime:
                print("Trying to create goss instance is timed out. ")
                raise TimeoutError
            else:
                continue
        else:
            print(goss_instance_id, " is STABLE.")
