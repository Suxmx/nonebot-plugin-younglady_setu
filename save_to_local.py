import os,glob
from pathlib import Path
import zipfile
import pyminizip
import string
import random
from typing import List

from anyio import open_file
from nonebot import get_driver
from nonebot.log import logger
from nonebot.utils import run_sync
from nonebot_plugin_setu_now.config import Config
from nonebot_plugin_setu_now.models import Setu
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    Message,
    GroupMessageEvent, PrivateMessageEvent,MessageSegment
)
rdmwords = string.ascii_lowercase + string.ascii_uppercase + string.digits + string.punctuation
                                         


plugin_config = Config.parse_obj(get_driver().config.dict())

setu_path = Path(plugin_config.setu_path) if plugin_config.setu_path else None
setu_directory=Path("E:/YoungLadyBot")
zip_path=setu_directory.joinpath("compress")
if not setu_path:
    setu_path = setu_directory.joinpath("imgs")
    
setur18_path = setu_path / "r18"

if setu_path.exists() and setur18_path.exists():
    logger.success(f"setu将保存到 {setu_path}")
else:
    os.makedirs(setu_path, exist_ok=True)
    os.makedirs(setur18_path, exist_ok=True)
    logger.success(f"创建文件夹 {setu_path}")
    logger.success(f"创建文件夹 {setur18_path}")
    logger.info(f"setu将保存到 {setu_path}")
    logger.info(f"r18setu将保存到 {setur18_path}")


async def save_img(setu: Setu):
    info = "{}_{}".format(setu.pid, setu.p)
    path = Path(f"{setu_path}{'/r18' if setu.r18 else '' }/{info}.jpg")
    async with await open_file(path, "wb+") as f:
        await f.write(setu.img)  # type: ignore
    logger.info(f"图片已保存 {path}")
    # if setu.r18 :
    #        logger.info("R18图片")
    # else :
    #        logger.info("非r18")


async def save_zip(bot:Bot,event:MessageEvent,data:list[Setu],filename:str,matcher):
    zip_filename=filename+".zip"
    
    logger.info(zip_path)
    if not zip_path.exists():
        os.makedirs(zip_path, exist_ok=True)
    #with zipfile.ZipFile(str(Path.cwd().joinpath("setu").joinpath(zip_filename)), 'w', zipfile.ZIP_DEFLATED) as z:
    imgpaths:List[str]=[]
    srcs:List[str]=[]
    #with zipfile.ZipFile(str(Path.cwd().joinpath("setu").joinpath(zip_filename)), 'w', zipfile.ZIP_DEFLATED) as z:
    for setu in data:
        imginfo = "{}_{}".format(setu.pid, setu.p)
        imgpath:Path=Path(f"{setu_path}{'/r18' if setu.r18 else '' }/{imginfo}.jpg")
        if imgpath.exists():
            imgpaths.append(str(imgpath))
            srcs.append("")
            logger.info(f"压缩包写入{imgpath}")
        else :
            logger.error(f"图片{imgpath}写入失败")
    if(srcs is not None):
        pwdchosen=random.sample(rdmwords,12)
        pwd="".join(pwdchosen)
        await matcher.send(message=Message(MessageSegment.text(f"密码{pwd}")), at_sender=True)
        pyminizip.compress_multiple(imgpaths,srcs,str(zip_path.joinpath(zip_filename)),pwd,1)
    else :
        return "EOF"
        #z.write(imgpath,f"{setu.pid}_{setu.p}.jpg")
    

    return str(zip_path.joinpath(zip_filename))
def delete():
    for file in glob.glob(str(zip_path.joinpath("*.zip"))):
        logger.info(f"已删除{zip_path}/{file}")
        os.remove(file)


        

