from pathlib import Path
from zipfile import ZipFile
from copy import deepcopy
from lxml import etree as E
import json
import hashlib

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / 'demand' / '北邮校园综合交互论坛_需求分析文档.docx'
WORK = ROOT / '.requirements_work' / 'fras-update'
WORK.mkdir(parents=True, exist_ok=True)
BASELINE = WORK / 'before-fras-update.docx'
DRAFT = WORK / 'updated-requirements.docx'
BASELINE.write_bytes(TARGET.read_bytes())
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{' + NS['w'] + '}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
PR = '{http://schemas.openxmlformats.org/package/2006/relationships}'
CT = '{http://schemas.openxmlformats.org/package/2006/content-types}'

def text(p):
    return ''.join(p.xpath('.//w:t/text()', namespaces=NS))

with ZipFile(BASELINE) as archive:
    infos = archive.infolist()
    parts = {i.filename: archive.read(i.filename) for i in infos}
doc = E.fromstring(parts['word/document.xml'])
body = doc.find('w:body', NS)
paras = body.findall('w:p', NS)
patterns = {'H1': deepcopy(paras[142]), 'H2': deepcopy(paras[18]), 'P': deepcopy(paras[19])}
original_sect = E.tostring(body.find('w:sectPr', NS))
changes = {
    '本系统是一项独立的 Web 应用，由用户界面、统一业务后端、数据库、缓存调度和文件存储组成。AI 模型通过外部接口提供需求解析能力；学校官方身份认证为条件具备时的可选接口，不是基础功能运行的前提。':
    '本系统是一项独立的 Web 应用，由用户界面、统一业务后端、数据库、缓存调度和文件存储组成。AI 模型通过外部接口提供需求解析能力；账户采用平台自主注册和登录，不接入校园 CAS。',
    '普通用户主要为北邮学生和教职工，具备基本网页操作能力。用户可发布内容、参与讨论、管理自己的商品和监控任务。认证师生角色仅在认证方案启用后使用；版主负责授权板块内的内容处理，管理员负责全站用户、板块、商品、举报、公告及任务管理。':
    '普通用户主要为北邮学生和教职工，具备基本网页操作能力。用户可发布内容、参与讨论、管理自己的商品和监控任务。平台角色包括普通用户、版主和管理员；版主负责授权板块内的内容处理，管理员负责全站用户、板块、商品、举报、公告及任务管理。自主注册不表示已经通过学校身份认证。',
    '（2）基础版采用平台自主注册和登录。校园邮箱验证或官方单点登录须在条件具备、认证方式获准后接入；不得收集、保存学校统一身份认证密码，也不得通过非官方抓取方式验证该密码。':
    '（2）基础版采用平台自主注册和登录，不接入校园 CAS，不设置学校认证师生角色。不得收集、保存学校统一身份认证密码，也不得通过非官方抓取方式验证该密码。',
    '输入：注册账户标识、平台密码、昵称；登录凭据；个人资料与头像；管理员提交的角色或账户状态变更。校园认证启用时接收获准认证渠道返回的必要身份信息。':
    '输入：注册账户标识、平台密码、昵称；登录凭据；个人资料与头像；管理员提交的角色或账户状态变更。注册登录仅接收平台自主账户信息。',
    '系统应支持本地运行及容器化部署，通过配置调整数据库、缓存、服务地址和模型参数。官方认证、对象存储和语义检索接口应具备可扩展性，扩展时保持基础论坛、交易和消息功能的兼容性。':
    '系统应支持本地运行及容器化部署，通过配置调整数据库、缓存、服务地址和模型参数。对象存储和语义检索接口应具备可扩展性，扩展时保持基础论坛、交易和消息功能的兼容性。校园 CAS 不属于本项目接口范围。',
    'AI 接口接收业务必要的需求文本并返回可校验的结构化条件，采用超时和失败处理；不向该接口传输平台密码或无关私聊。官方身份认证接口仅在取得接入条件后启用，接收必要身份信息，不接收或保存学校门户密码。接口字段、版本及认证参数需在详细设计中固定。':
    'AI 接口接收业务必要的需求文本并返回可校验的结构化条件，采用超时和失败处理；不向该接口传输平台密码或无关私聊。账户接口仅处理平台自主注册、登录与会话，不接入校园 CAS，不接收或保存学校门户密码。接口字段、版本及会话参数需在详细设计中固定。',
    '（1）校园认证：确认是否有官方单点登录授权或获准的校园邮箱验证方案，以及认证师生角色的启用条件；基础自主账户流程先行实现。':
    '（1）自主账户：确定注册标识、密码规则、账号恢复及会话续期和撤销策略；落实普通用户、版主、管理员的权限边界。校园 CAS 已明确不接入，不再作为待定事项。',
}

def replace_text(p, content):
    nodes = p.xpath('.//w:t', namespaces=NS)
    assert nodes
    nodes[0].text = content
    for node in nodes[1:]:
        node.text = ''

changed_paras = []
for p in paras:
    old = text(p)
    if old in changes:
        replace_text(p, changes[old])
        changed_paras.append(p)
assert len(changed_paras) == len(changes)

def element(parent, tag, **attrs):
    child = E.SubElement(parent, W + tag)
    for key, value in attrs.items():
        child.set(W + key, str(value))
    return child

def set_property(parent, tag, **attrs):
    for existing in parent.findall('w:' + tag, NS):
        parent.remove(existing)
    return element(parent, tag, **attrs)

def paragraph(content, kind='P', page_break=False):
    p = deepcopy(patterns[kind])
    rpr = p.find('w:r/w:rPr', NS)
    rpr = deepcopy(rpr) if rpr is not None else E.Element(W + 'rPr')
    for child in list(p):
        if child.tag != W + 'pPr':
            p.remove(child)
    pp = p.find('w:pPr', NS)
    if pp is None:
        pp = E.Element(W + 'pPr')
        p.insert(0, pp)
    set_property(pp, 'widowControl', val='1')
    set_property(rpr, 'color', val='000000')
    if kind.startswith('H'):
        set_property(pp, 'keepNext', val='1')
        set_property(pp, 'outlineLvl', val='0' if kind == 'H1' else '1')
        set_property(pp, 'spacing', before='180', after='100', line='360', lineRule='auto')
    if page_break:
        set_property(pp, 'pageBreakBefore', val='1')
    run = element(p, 'r')
    run.append(rpr)
    t = element(run, 't')
    t.text = content
    return p

sect = body.find('w:sectPr', NS)
new_elements = []
def append(node):
    body.insert(body.index(sect), node)
    new_elements.append(node)
    return node

def add(content, kind='P', page_break=False):
    return append(paragraph(content, kind, page_break))

def table(headers, rows, widths):
    tbl = E.Element(W + 'tbl')
    tp = element(tbl, 'tblPr')
    element(tp, 'tblW', w=sum(widths), type='dxa')
    element(tp, 'tblLayout', type='fixed')
    borders = element(tp, 'tblBorders')
    for side in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        element(borders, side, val='single', sz='4', color='D9D9D9')
    margins = element(tp, 'tblCellMar')
    for side, amount in [('top', 90), ('bottom', 90), ('left', 100), ('right', 100)]:
        element(margins, side, w=amount, type='dxa')
    grid = element(tbl, 'tblGrid')
    for width in widths:
        element(grid, 'gridCol', w=width)
    for row_no, row in enumerate([headers] + rows):
        tr = element(tbl, 'tr')
        trpr = element(tr, 'trPr')
        element(trpr, 'cantSplit')
        if row_no == 0:
            element(trpr, 'tblHeader')
        for col_no, cell_text in enumerate(row):
            tc = element(tr, 'tc')
            tcp = element(tc, 'tcPr')
            element(tcp, 'tcW', w=widths[col_no], type='dxa')
            element(tcp, 'vAlign', val='center')
            fill = 'E3EAF2' if row_no == 0 else ('F7F9FB' if row_no % 2 == 0 else 'FFFFFF')
            element(tcp, 'shd', val='clear', fill=fill)
            p = element(tc, 'p')
            pp = element(p, 'pPr')
            element(pp, 'spacing', after='0', line='270', lineRule='auto')
            element(pp, 'snapToGrid', val='0')
            if col_no == 0:
                element(pp, 'jc', val='center')
            else:
                element(pp, 'jc', val='left')
            run = element(p, 'r')
            rp = element(run, 'rPr')
            element(rp, 'rFonts', ascii='Times New Roman', hAnsi='Times New Roman', eastAsia='宋体')
            element(rp, 'sz', val='22')
            element(rp, 'color', val='000000')
            if row_no == 0:
                element(rp, 'b')
            element(run, 't').text = cell_text
    append(tbl)
    spacer = paragraph('')
    set_property(spacer.find('w:pPr', NS), 'spacing', after='100')
    append(spacer)

heading = add('5、FRAS 实验室网站用途与复用规划', 'H1', True)
add('本章明确 FRAS-lab-website 的业务用途、可借鉴模块及迁移边界。该仓库可为本项目的内容管理、管理界面和工程规范提供参考；本项目继续采用 Next.js 与 Rust 技术路线，自主开发论坛交互、交易、聊天和 AI 主动服务。')

add('5.1、仓库用途与实际技术结构', 'H2')
add('该仓库用于 FRAS 实验室官方网站，采用公开信息展示与管理员内容维护分离的结构。当前源码包含实验室介绍、研究方向、成员、科研成果、新闻、活动和轮播图，以及管理员登录、内容增删改查和图片／PDF 上传。它主要解决机构网站的内容发布与维护。')
add('后端采用 Java 21、Spring Boot 3.3.4、Spring Security、Spring Data JPA、MySQL、Flyway 和 JWT；前端采用 Vue 3、TypeScript、Vite、Vue Router、Axios 和 vue-i18n。仓库前端不是 Next.js，后端也不是 Rust。现有 Vue 单文件组件和 Java 服务无法直接并入本项目的 React／Rust 工程。')
add('源码中的公开接口与管理接口分开，新闻按发布状态过滤，管理端提供列表和编辑表单，数据库包含 V1 至 V13 的迁移。docs/CURRENT-VERSION.md 仍提到导师模块和较早迁移范围，而当前迁移 V10 已删除导师表，路由也已调整；复用判断应以本次检查的源码版本为准。')

add('5.2、可复用内容与改造方式', 'H2')
add('下表中的源码定位为仓库内相应目录下的文件名。复用分为设计参考、改写适配和有条件迁移；均不表示已迁移或已运行。')
table(['模块', '源码定位', '本项目用途', '复用方式'], [
    ['页面布局', 'style.css；PublicHeader.vue', '借鉴导航、卡片、列表和窄屏布局，建立论坛与商品页面的统一样式。', '参考布局；CSS 按需提取，界面改写为 React。'],
    ['管理界面', 'AdminDashboardView.vue；api/admin.ts', '借鉴列表、编辑、上传、加载和错误反馈，建设帖子、商品及公告管理页。', '参考交互；按业务拆分组件，补分页与权限。'],
    ['接口封装', 'api/client.ts；utils/auth.ts', '借鉴统一响应类型、请求超时和身份凭证注入。', 'TypeScript 逻辑可适配；调整路径、会话策略及错误处理。'],
    ['公开与管理接口', 'PublicController.java；AdminNewsController.java', '公开内容查询与管理操作分离；公告只展示有效发布内容。', '参考接口职责，在 Rust 中重写。'],
    ['内容维护', 'NewsService.java；NewsRepository.java', '借鉴创建、编辑、删除、发布状态和时间排序，适配公告等内容。', '参考业务流程；新增作者、板块、审核及分页。'],
    ['图片附件', 'AdminUploadController.java；FileStorageService.java', '借鉴上传表单、随机文件名和存储路径校验，用于头像、帖子和商品图片。', '参考上传链路；补真实类型检查及资源归属。'],
    ['数据库迁移', 'db/migration/V1—V13', '借鉴版本化建表、字段调整和初始化数据管理。', '重写为论坛迁移；不沿用实验室业务表。'],
    ['错误与部署', 'GlobalExceptionHandler.java；deploy.ps1', '借鉴校验错误响应、构建与健康检查的组织方式。', 'Rust 中重写；部署参数改为本项目配置。'],
], [1200, 2100, 3100, 1900])
add('中英双语使用独立语言资源及翻译数据表，适合作为未来国际化参考。首版使用中文界面，无需为普通论坛帖子复制双语表结构，也无需引入整套 vue-i18n 实现。实验室成员、成果、研究方向的数据仅用于理解原业务，不导入论坛用户或商品表。')

add('5.3、本项目仍需自主完成的功能', 'H2')
add('（1）账户与权限：该仓库提供管理员登录，但未提供论坛普通用户注册、普通用户／版主／管理员授权、板块权限和资源所属者控制。本项目自主账户需要独立设计。')
add('（2）论坛交流与二手交易：板块、帖子、评论回复、点赞收藏、作者编辑、商品价格与校区、商品状态和买卖双方联系流程均需新建，不能仅将新闻页面改名为帖子页面。')
add('（3）实时消息：当前已检查的源码未提供 WebSocket 私聊、会话历史、未读、离线补读和持久通知，应按需求文档分别建立聊天及通知模型。')
add('（4）AI 与搜索：当前源码未提供 LLM 需求提取、Embedding、全站语义检索、商品匹配和检索评测。需要共用 AI 服务、权限过滤及索引维护，不能把官网内容查询等同于论坛全站搜索。')
add('（5）周期监控与治理：商品增量匹配、任务领取、去重、暂停、失败重试、重启恢复，以及举报、封禁、版主管理和操作审计仍需开发。')

add('5.4、复用前必须处理的具体问题', 'H2')
add('认证与会话：JwtAuthFilter.java 将通过验签的凭证统一赋予 ROLE_ADMIN，符合原站管理员专用账户场景，不能用于论坛多角色授权；过滤器未在每次请求时重新查询账号状态。前端退出主要清理浏览器中的凭证，尚不能满足本项目的即时会话撤销和封禁要求。应重写角色校验、会话撤销及账号状态检查，不复制默认管理员账号或示例密钥。')
add('上传与访问：AdminUploadController.java 主要检查上传声明的 Content-Type，且未知 type 值没有明确拒绝；FileStorageService.java 提供随机名及路径边界检查。新实现需增加类型白名单、真实内容识别、图片解码、大小配额和资源归属；原公开文件接口不适合直接承担私有附件访问。')
add('查询与维护：NewsRepository.java 等示例以返回完整列表为主，不能满足论坛增长后的分页需求。管理端多个业务集中在单个较大的组件中，适配时应拆分页面与组件，加入分页、稳定排序、空状态和细粒度权限。')
add('环境与部署：Maven 配置和部署脚本包含原项目机器与服务器约定，并有清空远端前端目录的步骤；只借鉴构建、发布和健康检查的流程，不直接执行该脚本。新项目保持本地及 Docker Compose 路线，使用自身配置。')
add('许可与验证：本次取得的完整文件目录未发现 LICENSE 或 COPYING 文件，不能将公开可见等同于已经获得代码复制许可；复制代码前应确认许可或取得作者授权。仓库已有 contextLoads 启动测试，但仍需补论坛权限、上传、会话和异常测试。本次完成源码审阅，不将 README 中的构建说明作为本项目已构建或已验证的证据。')

add('5.5、三个参考仓库的职责分配', 'H2')
table(['仓库', '在本项目中的定位', '采用原则'], [
    ['hnu-doc', 'Rust 后端通用工程底座候选。', '核验后迁移启动、中间件、配置和连接池；替换学校认证及试卷模型。'],
    ['jhserver', '定时调度、通知与管理流程参考。', '借鉴方案并在 Rust 中实现；游戏邮件不能替代私聊或周期商品监控。'],
    ['FRAS-lab-website', '网页内容管理、界面和工程规范参考。', '优先参考界面、接口和迁移设计；Java/Vue 功能按 Rust/React 重写。'],
], [1900, 2600, 3800])
add('因此，增加此仓库作为参考不会自动改换后端语言或前端框架，也不增加第二套正式业务服务器。其价值主要在于减少界面与管理流程的设计工作，为现有路线提供可对照的实现。')

add('5.6、纳入当前两项规划的任务', 'H2')
add('统一需求：补充公告、管理列表、上传反馈、公开与私有资源边界的设计；为各可借鉴组件登记原用途、目标用途、技术差异和验收条件。保持不接入校园 CAS，保留平台自主注册与登录。')
add('底座核验与搭建：将 FRAS 仓库加入参考来源清单，记录固定提交和许可状态；按页面、接口、文件存储、数据迁移及部署分类核查。优先完成 Rust 基础工程及自主账户，FRAS 的管理界面和上传设计用于后续模块，不在当前搭建阶段宣称已经完成论坛或 AI 能力。')
add('验收应检查：自主账户与管理权限相互区分；列表能够分页；上传拒绝伪装类型与越权资源访问；管理操作可追溯；服务重启后业务数据仍在。AI 检索和监控在对应后续任务中单独验收。')

add('5.7、源码依据与检查版本', 'H2', True)
version_paragraph = add('检查日期为 2026 年 10 月 12 日；分支为 main，提交为 892e0b14d2a784c833597ecb9fc91f2a41b996d2。以下链接固定到本次检查的版本。')
set_property(version_paragraph.find('w:pPr', NS), 'jc', val='left')

rels = E.fromstring(parts['word/_rels/document.xml.rels'])
def link(label, path):
    p = paragraph('')
    set_property(p.find('w:pPr', NS), 'ind', firstLine='0')
    set_property(p.find('w:pPr', NS), 'jc', val='left')
    rid = 'rIdFrasSource' + str(len(rels) + 1)
    relation = E.SubElement(rels, PR + 'Relationship')
    relation.set('Id', rid)
    relation.set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink')
    relation.set('Target', 'https://github.com/gygy-hh/FRAS-lab-website/blob/892e0b14d2a784c833597ecb9fc91f2a41b996d2/' + path)
    relation.set('TargetMode', 'External')
    h = E.SubElement(p, W + 'hyperlink')
    h.set(R + 'id', rid)
    run = element(h, 'r')
    rp = element(run, 'rPr')
    element(rp, 'color', val='1F4E79')
    element(rp, 'u', val='single')
    element(run, 't').text = label
    append(p)

for label, path in [
    ('项目说明与功能范围：README.md', 'README.md'),
    ('后端依赖与 Java 版本：backend/pom.xml', 'backend/pom.xml'),
    ('前端依赖与构建：frontend/package.json', 'frontend/package.json'),
    ('管理界面与操作流程：AdminDashboardView.vue', 'frontend/src/views/admin/AdminDashboardView.vue'),
    ('新闻状态过滤与内容维护：NewsService.java', 'backend/src/main/java/com/fraslab/site/service/NewsService.java'),
    ('角色处理：JwtAuthFilter.java', 'backend/src/main/java/com/fraslab/site/security/JwtAuthFilter.java'),
    ('上传检查：AdminUploadController.java', 'backend/src/main/java/com/fraslab/site/controller/AdminUploadController.java'),
    ('文件路径与存储：FileStorageService.java', 'backend/src/main/java/com/fraslab/site/service/FileStorageService.java'),
    ('版本化迁移示例：V13__carousel_images.sql', 'backend/src/main/resources/db/migration/V13__carousel_images.sql'),
    ('环境与发布流程：deploy.ps1', 'deploy.ps1'),
]:
    link(label, path)

# Add review comments at the changed paragraphs and added section, keeping body text clean.
comments = E.Element(W + 'comments', nsmap={'w': NS['w']})
def comment(p, comment_id, content):
    start = E.Element(W + 'commentRangeStart')
    start.set(W + 'id', str(comment_id))
    pp = p.find('w:pPr', NS)
    p.insert(1 if pp is not None else 0, start)
    element(p, 'commentRangeEnd', id=comment_id)
    rr = element(p, 'r')
    element(rr, 'commentReference', id=comment_id)
    c = element(comments, 'comment', id=comment_id, author='Codex', date='2026-10-12T00:00:00Z')
    cp = element(c, 'p')
    cr = element(cp, 'r')
    element(cr, 't').text = content

for i, p in enumerate(changed_paras):
    comment(p, i, '按已确认的项目范围，采用平台自主账户，不接入校园 CAS；同步移除学校认证接口和角色的条件性表述。')
comment(heading, len(changed_paras), '新增 FRAS-lab-website 的源码用途、复用映射、技术差异、待开发功能及固定版本来源。仓库构建与运行不在本次文档分析中声明完成。')
rid = 'rIdFrasComments'
relation = E.SubElement(rels, PR + 'Relationship')
relation.set('Id', rid)
relation.set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments')
relation.set('Target', 'comments.xml')
content_types = E.fromstring(parts['[Content_Types].xml'])
override = E.SubElement(content_types, CT + 'Override')
override.set('PartName', '/word/comments.xml')
override.set('ContentType', 'application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml')

def xml_bytes(root):
    return E.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)

assert E.tostring(sect) == original_sect
parts['word/document.xml'] = xml_bytes(doc)
parts['word/_rels/document.xml.rels'] = xml_bytes(rels)
parts['[Content_Types].xml'] = xml_bytes(content_types)
parts['word/comments.xml'] = xml_bytes(comments)
with ZipFile(DRAFT, 'w') as archive:
    for info in infos:
        archive.writestr(info, parts[info.filename])
    archive.writestr('word/comments.xml', parts['word/comments.xml'])

with ZipFile(BASELINE) as before, ZipFile(DRAFT) as after:
    changed_parts = [name for name in before.namelist() if before.read(name) != after.read(name)]
    assert set(changed_parts) == {'word/document.xml', 'word/_rels/document.xml.rels', '[Content_Types].xml'}
    for name in after.namelist():
        if name.endswith(('.xml', '.rels')):
            E.fromstring(after.read(name))
all_text = '\n'.join(text(p) for p in body.xpath('.//w:p', namespaces=NS))
assert '官方身份认证接口仅在取得接入条件后启用' not in all_text
assert '认证师生角色仅在认证方案启用后使用' not in all_text
assert '5.7、源码依据与检查版本' in all_text
assert len(body.findall('w:tbl', NS)) == 2
assert len(comments) == 8
evidence = {
    'target': str(TARGET), 'draft': str(DRAFT), 'backup': str(BASELINE),
    'source_sha256': hashlib.sha256(BASELINE.read_bytes()).hexdigest(),
    'changed_existing_paragraphs': len(changed_paras), 'appended_elements': len(new_elements),
    'comments': len(comments), 'changed_existing_parts': changed_parts,
    'preserved_cover_media_styles_and_section': True,
    'repo_commit': '892e0b14d2a784c833597ecb9fc91f2a41b996d2',
}
(WORK / 'structural-verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), 'utf-8')
print(json.dumps(evidence, ensure_ascii=False))
