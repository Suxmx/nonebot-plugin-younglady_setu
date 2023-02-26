import asyncio
import time
from re import I, sub
from typing import List
from asyncio import sleep, create_task
from asyncio.tasks import Task

from nonebot import on_regex, get_driver
from nonebot.log import logger
from nonebot.typing import T_State
from nonebot.exception import ActionFailed
from nonebot.adapters.onebot.v11 import (
    GROUP,
    PRIVATE_FRIEND,
    Bot,
    Message,
    MessageEvent,
    MessageSegment,
    GroupMessageEvent,
    PrivateMessageEvent,
)

from .utils import send_forward_msg,send_private_forward_msg
from .config import Config
from .models import Setu, SetuNotFindError
from .withdraw import add_withdraw_job
from .cd_manager import add_cd, cd_msg, check_cd, remove_cd
from .data_source import SetuLoader
from .save_to_local import save_zip,delete
from nonebot.adapters.onebot.v11 import (MessageSegment, Message,
                                         ActionFailed, NetworkError, Bot,
                                         GroupMessageEvent, PrivateMessageEvent)

plugin_config = Config.parse_obj(get_driver().config.dict())
SAVE = plugin_config.setu_save
SETU_SIZE = plugin_config.setu_size
MAX = plugin_config.setu_max
EFFECT = plugin_config.setu_add_random_effect

if SAVE == "webdav":
    from .save_to_webdav import save_img
elif SAVE == "local":
    delete()
    from .save_to_local import save_img


plugin_config = Config.parse_obj(get_driver().config.dict())

setu_matcher0 = on_regex(
    r"^(setu|色图|涩图|来点色色|色色|涩涩|来点色图)\s?([x|✖️|×|X|*]?\d+[张|个|份]?)?\s?(r18)?\s?(zip)?\s?(tag)?\s?(.*)?",
    flags=I,
    permission=PRIVATE_FRIEND | GROUP,
)
setu_matcher1 = on_regex(
    r"^(爹|爸|爹爹|爸爸|父亲|爷爷)\s?(setu|色图|涩图|来点色色|色色|涩涩|来点色图)\s?([x|✖️|×|X|*]?\d+[张|个|份]?)?\s?(r18)?(zip)?\s?\s?(tag)?\s?(.*)?",
    flags=I,
    permission=PRIVATE_FRIEND | GROUP,
)
setu_matcher2 = on_regex(
    r"^group(setu|色图|涩图|来点色色|色色|涩涩|来点色图)\s?([x|✖️|×|X|*]?\d+[张|个|份]?)?\s?(r18)?\s?(zip)?\s?(tag)?\s?(.*)?",
    flags=I,
    permission=PRIVATE_FRIEND | GROUP,
)
#######################################################
async def upload_group_file(bot: Bot, event: MessageEvent, file, name,matcher):
        msg=MessageSegment.text("开始上传压缩包")
        await matcher.send(msg, at_sender=True)
        try:
            await bot.upload_group_file(group_id=event.group_id,
                                             file=file, name=name)
        except (ActionFailed, NetworkError) as e:
            logger.error(e)
            if isinstance(e, ActionFailed) and e.info["wording"] == "server" \
                                                                    " requires unsupported ftn upload":
                await bot.send(event=event, message=Message(MessageSegment.text(
                    "[ERROR]  文件上传失败\r\n[原因]  机器人缺少上传文件的权限\r\n[解决办法]  "
                    "请将机器人设置为管理员或者允许群员上传文件")))
            elif isinstance(e, NetworkError):
                await bot.send(event=event, message=Message(MessageSegment.text(
                    "[ERROR]  文件上传失败\r\n[原因]  上传超时(一般来说还在传,建议等待五分钟)")))
                
async def upload_private_file(bot: Bot, event: MessageEvent, file, name,matcher):
        msg=MessageSegment.text("开始上传压缩包")
        await matcher.send(msg, at_sender=True)
        try:
            await bot.upload_private_file(user_id=event.user_id,
                                               file=file, name=name)
        except (ActionFailed, NetworkError) as e:
            logger.error(e)
            if isinstance(e, NetworkError):
                await bot.send(event=event, message=Message(MessageSegment.text(
                    "[ERROR]  文件上传失败\r\n[原因]  上传超时(一般来说还在传,建议等待五分钟)")))
############################################################
@setu_matcher0.handle()
async def _(bot: Bot, event: MessageEvent, state: T_State):
    
    args = list(state["_matched_groups"])
    
    num = args[1]
    r18 = args[2]
    ifzip=args[3]
    tags = args[4]
    key = args[5]
    num = int(sub(r"[张|个|份|x|✖️|×|X|*]", "", num)) if num else 1
    if num > MAX:
        num = MAX

    # 如果存在 tag 关键字, 则将 key 视为tag
    if tags:
        tags = list(map(lambda l: l.split("或"), key.split()))
        key = ""

    # 仅在私聊中开启
    r18 = True if ((isinstance(event, PrivateMessageEvent )or ifzip) and r18) else False
    if cd := check_cd(event):
        # 如果 CD 还没到 则直接结束
        await setu_matcher0.finish(cd_msg(cd), at_sender=True)
    logger.debug(f"Setu: r18:{r18}, tag:{tags}, key:{key}, num:{num}")
    add_cd(event, num)

    setu_obj = SetuLoader()
    try:
        data = await setu_obj.get_setu(key, tags, r18, num)
        ##########################上传zip##########################
        if ifzip and num>1:
            curTime=time.strftime("%Y-%m-%d-%H-%M-%S",time.localtime())
            curTime= curTime if not r18 else "R18-"+curTime
            zipname= await save_zip(bot,event,data=data,filename=curTime,matcher=setu_matcher0)
            if zipname is not"EOF":
                logger.success(f"生成压缩文件{zipname}")
            else :
                logger.error("生成压缩文件失败:待写入文件为空!")
                await setu_matcher0.finish("生成压缩文件失败!一次性多生成图片可提高成功率", at_sender=True)
            if isinstance(event,PrivateMessageEvent):
                await upload_private_file(bot,event,zipname,f"{curTime}.zip",matcher=setu_matcher0)
            elif isinstance(event,GroupMessageEvent):
                await upload_group_file(bot,event,zipname,f"{curTime}.zip",matcher=setu_matcher0)
        elif num==1 and ifzip:
            await setu_matcher0.finish("一个文件请勿使用压缩包", at_sender=True)
        ##########################上传zip##########################
    except SetuNotFindError:
        remove_cd(event)
        await setu_matcher0.finish(f"没有找到关于 {tags or key} 的色图呢～", at_sender=True)

    failure_msg: int = 0
    msg_list: List[Message] = []
    setu_saving_tasks: List[Task] = []

    for setu in data:
        msg = Message(MessageSegment.image(setu.img))  # type: ignore

        if plugin_config.setu_send_info_message:
            msg.append(MessageSegment.text(setu.msg))  # type: ignore

        msg_list.append(msg)  # type: ignore

        if SAVE and EFFECT is False:
            setu_saving_tasks.append(create_task(save_img(setu)))
    


        # 私聊 或者 群聊中 <= 3 图, 直接发送
    if (isinstance(event, PrivateMessageEvent) or len(data) <= 3)and not ifzip:
        for msg in msg_list:
            try:
                msg_info = await setu_matcher0.send(msg, at_sender=True)
                add_withdraw_job(bot, **msg_info)
                await sleep(2)

            except ActionFailed as e:
                logger.warning(e)
                failure_msg += 1

    # 群聊中 > 3 图, 合并转发
    elif isinstance(event, GroupMessageEvent)and not ifzip:

        try:
            await send_forward_msg(bot, event, "土豆看了都震惊", bot.self_id, msg_list)
        except ActionFailed as e:
            logger.warning(e)
            failure_msg = num

    if failure_msg >= num / 2:
        remove_cd(event)

        await setu_matcher0.finish(
            message=Message(f"消息被风控，{failure_msg} 个图发不出来了\n"),
            at_sender=True,
        )

    await asyncio.gather(*setu_saving_tasks)
    


@setu_matcher1.handle()
async def _(bot: Bot, event: MessageEvent, state: T_State):
    args = list(state["_matched_groups"])
    num = args[2]
    r18 = args[3]
    tags = args[4]
    key = args[5]

    num = int(sub(r"[张|个|份|x|✖️|×|X|*]", "", num)) if num else 1
    if num > MAX:
        num = MAX

    # 如果存在 tag 关键字, 则将 key 视为tag
    if tags:
        tags = list(map(lambda l: l.split("或"), key.split()))
        key = ""

    # 仅在私聊中开启
    r18 = True if (isinstance(event, PrivateMessageEvent) and r18) else False

    # if cd := check_cd(event):
    #     # 如果 CD 还没到 则直接结束
    #     await setu_matcher1.finish(cd_msg(cd), at_sender=True)

    logger.debug(f"Setu: r18:{r18}, tag:{tags}, key:{key}, num:{num}")
    add_cd(event, num)

    setu_obj = SetuLoader()
    try:
        data = await setu_obj.get_setu(key, tags, r18, num)
    except SetuNotFindError:
        remove_cd(event)
        await setu_matcher1.finish(f"没有找到关于 {tags or key} 的色图呢～", at_sender=True)

    failure_msg: int = 0
    msg_list: List[Message] = []
    setu_saving_tasks: List[Task] = []

    for setu in data:
        msg = Message(MessageSegment.image(setu.img))  # type: ignore

        if plugin_config.setu_send_info_message:
            msg.append(MessageSegment.text(setu.msg))  # type: ignore

        msg_list.append(msg)  # type: ignore

        if SAVE and EFFECT is False:
            setu_saving_tasks.append(create_task(save_img(setu)))
        

        # 私聊 或者 群聊中 <= 3 图, 直接发送
    if isinstance(event, PrivateMessageEvent) or len(data) <= 3:
        for msg in msg_list:
            try:
                msg_info = await setu_matcher1.send(msg, at_sender=True)
                add_withdraw_job(bot, **msg_info)
                await sleep(2)

            except ActionFailed as e:
                logger.warning(e)
                failure_msg += 1

    # 群聊中 > 3 图, 合并转发
    elif isinstance(event, GroupMessageEvent):

        try:
            await send_forward_msg(bot, event, "爹", bot.self_id, msg_list)
        except ActionFailed as e:
            logger.warning(e)
            failure_msg = num

    if failure_msg >= num / 2:
        remove_cd(event)

        await setu_matcher1.finish(
            message=Message(f"消息被风控，{failure_msg} 个图发不出来了\n"),
            at_sender=True,
        )

    await asyncio.gather(*setu_saving_tasks)
@setu_matcher2.handle()
async def _(bot: Bot, event: MessageEvent, state: T_State):
    args = list(state["_matched_groups"])
    num = args[1]
    r18 = args[2]
    tags = args[3]
    key = args[4]

    num = int(sub(r"[张|个|份|x|✖️|×|X|*]", "", num)) if num else 1
    if num > MAX:
        num = MAX

    # 如果存在 tag 关键字, 则将 key 视为tag
    if tags:
        tags = list(map(lambda l: l.split("或"), key.split()))
        key = ""

    # 仅在私聊中开启
    r18 = True if (isinstance(event, PrivateMessageEvent) and r18) else False

    if cd := check_cd(event):
        # 如果 CD 还没到 则直接结束
        await setu_matcher2.finish(cd_msg(cd), at_sender=True)

    logger.debug(f"Setu: r18:{r18}, tag:{tags}, key:{key}, num:{num}")
    add_cd(event, num)

    setu_obj = SetuLoader()
    try:
        data = await setu_obj.get_setu(key, tags, r18, num)
    except SetuNotFindError:
        remove_cd(event)
        await setu_matcher2.finish(f"没有找到关于 {tags or key} 的色图呢～", at_sender=True)

    failure_msg: int = 0
    msg_list: List[Message] = []
    setu_saving_tasks: List[Task] = []

    for setu in data:
        msg = Message(MessageSegment.image(setu.img))  # type: ignore

        if plugin_config.setu_send_info_message:
            msg.append(MessageSegment.text(setu.msg))  # type: ignore

        msg_list.append(msg)  # type: ignore

        if SAVE and EFFECT is False:
            setu_saving_tasks.append(create_task(save_img(setu)))
        

        # 私聊合并发送
    if isinstance(event, PrivateMessageEvent):
        try:
            await send_private_forward_msg(bot, event, "Yane", bot.self_id, msg_list)
        except ActionFailed as e:
            logger.warning(e)
            failure_msg += 1

    # 群聊合并转发
    elif isinstance(event, GroupMessageEvent):

        try:
            await send_forward_msg(bot, event, "Yane", bot.self_id, msg_list)
        except ActionFailed as e:
            logger.warning(e)
            failure_msg = num

    if failure_msg >= num / 2:
        remove_cd(event)

        await setu_matcher2.finish(
            message=Message(f"消息被风控，{failure_msg} 个图发不出来了\n"),
            at_sender=True,
        )

    await asyncio.gather(*setu_saving_tasks)
