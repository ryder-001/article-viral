from .wechat import WechatCollector
from .toutiao import ToutiaoCollector
from .baijiahao import BaijiahaoCollector
from .weibo import WeiboCollector
from .sohu import SohuCollector
from .zhihu import ZhihuCollector

ALL_COLLECTORS = {
    "wechat": WechatCollector,
    "toutiao": ToutiaoCollector,
    "baijiahao": BaijiahaoCollector,
    "weibo": WeiboCollector,
    "sohu": SohuCollector,
    "zhihu": ZhihuCollector,
}
