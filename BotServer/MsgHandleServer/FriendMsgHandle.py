from BotServer.BotFunction.InterfaceFunction import *
from ApiServer.AiServer.AiDialogue import AiDialogue
from BotServer.BotFunction.JudgeFuncion import *
from DbServer.DbMainServer import DbMainServer
import xml.etree.ElementTree as ET
import Config.ConfigServer as Cs
from OutPut.outPut import op
from threading import Thread
import time
import xml.etree.ElementTree as ET

class FriendMsgHandle:
    def __init__(self, wcf):
        """
        关键词拉群 yes
        好友消息转发给超管 yes
        好友Ai消息 yes
        自定义关键词回复 yes
        管理员公众号消息转发给推送群聊 yes
        查看白名单群聊 yes
        查看黑名单群聊 yes
        查看推送群聊 yes
        查看黑名单公众号 yes
        好友红包消息处理 yes
        好友转账接收 yes 微信版本过低无法使用
        :param wcf:
        """
        self.wcf = wcf
        self.Ad = AiDialogue()
        self.Dms = DbMainServer()
        configData = Cs.returnConfigData()
        # 超级管理员列表
        self.Administrators = configData['Administrators']
        # 给好友发消息关键词
        self.sendMsgKeyWords = configData['adminFunctionWord']['sendMsgWord']
        # Ai锁
        self.aiLock = configData['systemConfig']['aiLock']
        # 转账接收锁
        self.acceptMoneyLock = configData['systemConfig']['acceptMoneyLock']
        # 自动同意好友锁
        self.acceptFriendLock = configData['systemConfig']['acceptFriendLock']
        # 进群关键词字典
        self.roomKeyWords = configData['roomKeyWord']
        # 自定义回复关键词字典
        self.customKeyWords = configData['customKeyWord']
        # 查看白名单群聊关键词
        self.showWhiteRoomKeyWords = configData['adminFunctionWord']['showWhiteRoomWord']
        # 查看黑名单群聊关键词
        self.showBlackRoomKeyWords = configData['adminFunctionWord']['showBlackRoomWord']
        # 查看推送群聊关键词
        self.showPushRoomKeyWords = configData['adminFunctionWord']['showPushRoomWord']
        # 查看黑名单公众号关键词
        self.showBlackGhKeyWords = configData['adminFunctionWord']['showBlackGhWord']
        # 添加好友后自动回复消息
        self.acceptFriendMsg = configData['customMsg']['acceptFriendMsg']
        # 好友消息转发给管理员开关
        self.msgForwardAdmin = configData['systemConfig']['msgForwardAdmin']
        # 记录每个好友已经匹配过的关键词
        self.matched_keywords = {}

    def mainHandle(self, msg):
        content = msg.content.strip()
        sender = msg.sender
        msgType = msg.type

        if msgType == 1:
            # 关键词进群
            if judgeEqualListWord(content, self.roomKeyWords.keys()):
                # self.keyWordJoinRoom(sender, content)
                Thread(target=self.keyWordJoinRoom, args=(sender, content)).start()
            # 自定义关键词回复功能，改成模糊匹配
            # elif judgeEqualListWord(content, self.customKeyWords.keys()):
            elif judgeInListWord(content, self.customKeyWords.keys()):
                # self.customKeyWordMsg(sender, content)
                Thread(target=self.customKeyWordMsg, args=(sender, content)).start()
            # 查看白名单群聊
            elif judgeEqualListWord(content, self.showWhiteRoomKeyWords) and sender in self.Administrators:
                # self.showWhiteRoom(sender, )
                Thread(target=self.showWhiteRoom, args=(sender,)).start()
            # 查看黑名单群聊
            elif judgeEqualListWord(content, self.showBlackRoomKeyWords) and sender in self.Administrators:
                # self.showBlackRoom(sender, )
                Thread(target=self.showBlackRoom, args=(sender,)).start()
            # 查看推送群聊
            elif judgeEqualListWord(content, self.showPushRoomKeyWords) and sender in self.Administrators:
                # self.showPushRoom(sender, )
                Thread(target=self.showPushRoom, args=(sender,)).start()
            # 查看黑名单公众号
            elif judgeEqualListWord(content, self.showBlackGhKeyWords) and sender in self.Administrators:
                # self.showBlackGh(sender, )
                Thread(target=self.showBlackGh, args=(sender,)).start()
            # Ai对话 Ai锁功能 对超管没用
            # elif self.aiLock or sender in self.Administrators:
            # elif not self.aiLock and sender not in self.Administrators:
            #     Thread(target=self.getAiMsg, args=(content, sender)).start()
            # 超级管理员发消息转发给好友
            if judgeSplitAllEqualWord(content, self.sendMsgKeyWords):
                Thread(target=self.sendFriendMsg, args=(content,)).start()
            # 好友消息转发给超级管理员 超级管理员不触发
            if sender not in self.Administrators and self.msgForwardAdmin:
                Thread(target=self.forwardMsgToAdministrators, args=(sender, content)).start()
        # 转发公众号消息到推送群聊 超管有效
        if msg.type == 49:
            if msg.sender in self.Administrators and 'gh_' in msg.content:
                Thread(target=self.forwardGhMsg, args=(msg.id,)).start()
            # 暂时没用 等Hook作者更新 老版本微信有用
            elif '转账' in msg.content and self.acceptMoneyLock:
                Thread(target=self.acceptMoney, args=(msg,)).start()
            elif msg.type == 49 and sender in self.Administrators and '好友ID:' in msg.content:
                Thread(target=self.forwardRefMsgToAdministrators, args=(content,)).start()
        # 红包消息处理 转发红包消息给主人
        if msgType == 10000 and '请在手机上查看' in msg.content:
            Thread(target=self.forwardRedPacketMsg, args=(sender,)).start()
        # 好友自动同意处理 暂时没用 老版本微信有用
        if msgType == 37 and self.acceptFriendLock:
            Thread(target=self.acceptFriend, args=(msg,)).start()
        # 管理员引用消息，将内容转发给好友
        # if msgType == 57:
        #     Thread(target=self.forwardRefMsgToAdministrators, args=(msg,)).start()

    def acceptFriend(self, msg):
        """
        同意好友申请处理
        :return:
        """
        root_xml = ET.fromstring(msg.content.strip())
        wxId = root_xml.attrib["fromusername"]
        op(f'[*]: 接收到新的好友申请, 微信id为: {wxId}')
        v3 = root_xml.attrib["encryptusername"]
        v4 = root_xml.attrib["ticket"]
        scene = int(root_xml.attrib["scene"])
        ret = self.wcf.accept_new_friend(v3=v3, v4=v4, scene=scene)
        acceptSendMsg = self.acceptFriendMsg.replace('\\n', '\n')
        self.wcf.send_text(acceptSendMsg, receiver=wxId)
        if ret:
            op(f'[+]: 好友 {self.wcf.get_info_by_wxid(wxId).get("name")} 已自动通过 !')
        else:
            op(f'[-]: 好友通过失败！！！')

    def acceptMoney(self, msg):
        """
        处理转账消息, 只处理好友转账
        :param msg:
        :return:
        """
        root_xml = ET.fromstring(msg.content.strip())
        title_element = root_xml.find(".//title")
        title = title_element.text if title_element is not None else None
        if '微信转账' == title and msg.sender != self.wcf.self_wxid:
            transCationId = root_xml.find('.//transcationid').text
            transFerid = root_xml.find('.//transferid').text
            if not self.wcf.receive_transfer(wxid=msg.sender, transactionid=transCationId,
                                             transferid=transFerid):
                op(f'[-]: 接收好友转账失败, 可能是版本不支持')

    def forwardRedPacketMsg(self, sender):
        """
        转发红包消息给主人
        :return:
        """
        for administrator in self.Administrators:
            self.wcf.send_text(f'[爱心]接收到好友: {getIdName(self.wcf, sender)} 的红包, 请在手机上接收',
                               receiver=administrator)
        self.wcf.send_text(f'[爱心]已接收到您的红包, 感谢支持', receiver=sender)

    def showBlackGh(self, sender):
        """
        查看黑名单公众号
        :param sender:
        :return:
        """
        blackGhData = self.Dms.showBlackGh()
        sendMsg = '===== 推送群聊列表 =====\n'
        for roomId, roomName in blackGhData.items():
            sendMsg += f'公众号ID: {roomId}\n公众号昵称: {roomName}\n---------------\n'
        if not blackGhData:
            sendMsg = '暂无公众号添加至黑名单'
        self.wcf.send_text(sendMsg, receiver=sender)

    def showPushRoom(self, sender):
        """
        查看推送群聊
        :param sender:
        :return:
        """
        pushRoomData = self.Dms.showPushRoom()
        sendMsg = '===== 推送群聊列表 =====\n'
        for roomId, roomName in pushRoomData.items():
            sendMsg += f'群聊ID: {roomId}\n群聊昵称: {roomName}\n---------------\n'
        if not pushRoomData:
            sendMsg = '暂无群聊开启推送服务'
        self.wcf.send_text(sendMsg, receiver=sender)

    def showBlackRoom(self, sender):
        """
        查看黑名单群聊 超管有效
        :return:
        """
        blackRoomData = self.Dms.showBlackRoom()
        sendMsg = '===== 黑名单群聊列表 =====\n'
        for roomId, roomName in blackRoomData.items():
            sendMsg += f'群聊ID: {roomId}\n群聊昵称: {roomName}\n---------------\n'
        if not blackRoomData:
            sendMsg = '暂无群聊添加至黑名单'
        self.wcf.send_text(sendMsg, receiver=sender)

    def showWhiteRoom(self, sender):
        """
        查看白名单群聊 超管有效
        :return:
        """
        whiteRoomData = self.Dms.showWhiteRoom()
        sendMsg = '===== 白名单群聊列表 =====\n'
        for roomId, roomName in whiteRoomData.items():
            sendMsg += f'群聊ID: {roomId}\n群聊昵称: {roomName}\n---------------\n'
        if not whiteRoomData:
            sendMsg = '暂无群聊添加至白名单'
        self.wcf.send_text(sendMsg, receiver=sender)

    def forwardGhMsg(self, msgId):
        """
        转发公众号消息到推送群来哦 超管有效
        :param msgId:
        :return:
        """
        pushRoomDicts = self.Dms.showPushRoom()
        for pushRoomId in pushRoomDicts.keys():
            self.wcf.forward_msg(msgId, receiver=pushRoomId)

    def customKeyWordMsg(self, sender, content):
        """
        自定义关键词消息回复
        :param sender: 发送者
        :param content: 好友发送的消息内容
        :return:
        """
        # 添加3秒的延迟
        time.sleep(3)
        if sender not in self.matched_keywords:
            self.matched_keywords[sender] = set()

        # if content not in self.matched_keywords[sender]:
            # responses = self.customKeyWords.get(content, [])
            # for response in responses:
            #     if response.startswith('image:'):
            #         picPath = response[6:]  # 去掉 'image:' 前缀
            #         self.wcf.send_image(picPath, receiver=sender)
            #     else:
            #         self.wcf.send_text(response, receiver=sender)
            # self.matched_keywords[sender].add(content)
        for word in self.customKeyWords.keys():
            if word in content:
                if word not in self.matched_keywords[sender]:
                    responses = self.customKeyWords.get(word, [])
                    op(f'[+]: responses=== {responses} ')
                    for response in responses:
                        if response.startswith('image:'):
                            picPath = response[6:]  # 去掉 'image:' 前缀
                            op(f'[+]: picPath=== {picPath} ')
                            self.wcf.send_image(picPath, receiver=sender)
                        else:
                            self.wcf.send_text(response, receiver=sender)
                    self.matched_keywords[sender].add(word)


    def keyWordJoinRoom(self, sender, content):
        """
        关键词进群
        :param sender:
        :param content:
        :return:
        """
        for keyWord in self.roomKeyWords.keys():
            if judgeEqualWord(content, keyWord):
                roomLists = self.roomKeyWords.get(keyWord)
                for roomId in roomLists:
                    roomMember = self.wcf.get_chatroom_members(roomId)
                    if len(roomMember) == 500:
                        continue
                    if sender in roomMember.keys():
                        self.wcf.send_text(f'你小子已经进群了, 还想干吗[旺柴]', receiver=sender)
                        break
                    if self.wcf.invite_chatroom_members(roomId, sender):
                        op(f'[+]: 已将 {sender} 拉入群聊【{roomId}】')
                        break
                    else:
                        op(f'[-]: {sender} 拉入群聊【{roomId}】失败 !!!')

    def sendFriendMsg(self, content):
        """
        给好友发消息 只对超管生效
        :param content:
        :return:
        """
        wxId = content.split(' ')[1]
        # sendMsg = f'==== [爱心]来自超管的消息[爱心] ====\n\n{content.split(" ")[-1]}\n\n====== [爱心]NGCBot[爱心] ======'
        sendMsg = content.split(" ")[-1]
        self.wcf.send_text(sendMsg, receiver=wxId)

    def getAiMsg(self, content, sender):
        """
        好友Ai对话
        :param content:
        :param sender:
        :return:
        """
        aiMsg = self.Ad.getAi(content)
        if aiMsg:
            self.wcf.send_text(aiMsg, receiver=sender)
            return
        self.wcf.send_text(f'Ai对话接口出现错误, 请稍后再试 ~~~', receiver=sender)

    def forwardMsgToAdministrators(self, wxId, content):
        """
        好友消息转发给超级管理员
        :param wxId:
        :param content:
        :return:
        """
        forwardMsg = f"= [爱心]收到来自好友的消息[爱心] =\n好友ID: {wxId}\n好友昵称: {getIdName(self.wcf, wxId)}\n好友消息: {content}\n====== [爱心]NGCBot[爱心] ======"
        for administrator in self.Administrators:
            self.wcf.send_text(forwardMsg, receiver=administrator)

    @staticmethod
    def extract_wxid_and_title_from_xml(content: str):
        # 解析XML内容
        root = ET.fromstring(content)
        # 查找refermsg节点
        refermsg_node = root.find('.//refermsg')
        wxId = None
        title = None
        if refermsg_node is not None:
            # 查找content节点
            content_node = refermsg_node.find('content')
            if content_node is not None:
                content_text = content_node.text
                # 使用正则表达式提取wxid
                import re
                match = re.search(r'好友ID: (\w+)', content_text)
                if match:
                    wxId = match.group(1)
        # 查找title节点
        title_node = root.find('.//title')
        if title_node is not None:
            title = title_node.text
        return wxId, title
    def forwardRefMsgToAdministrators(self, content):
        """
        好友消息转发给超级管理员 引用的方式
        :param content:
        :return:
        """
        wxId, title = self.extract_wxid_and_title_from_xml(content)
        # sendMsg = f'==== [爱心]来自超管的消息[爱心] ====\n\n{content.split(" ")[-1]}\n\n====== [爱心]NGCBot[爱心] ======'
        # sendMsg = content.split(" ")[-1]
        if wxId:
            self.wcf.send_text(title, receiver=wxId)
        else:
            print("未匹配到wxId")



if __name__ == '__main__':
    Fmh = FriendMsgHandle(1)
    Fmh.showWhiteRoom()
