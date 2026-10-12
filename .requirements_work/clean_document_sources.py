from pathlib import Path
from zipfile import ZipFile
from copy import deepcopy
from lxml import etree as E
import hashlib
import json

root = Path(__file__).resolve().parent.parent
target = root / 'demand' / '北邮校园综合交互论坛_需求分析文档.docx'
work = root / '.requirements_work' / 'requirements-cleanup'
work.mkdir(parents=True, exist_ok=True)
baseline = work / 'before-cleanup.docx'
draft = work / 'updated-requirements.docx'
baseline.write_bytes(target.read_bytes())
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{' + ns['w'] + '}'
PR = '{http://schemas.openxmlformats.org/package/2006/relationships}'
with ZipFile(baseline) as archive:
    infos = archive.infolist()
    parts = {info.filename: archive.read(info.filename) for info in infos}
document = E.fromstring(parts['word/document.xml'])
body = document.find('w:body', ns)
def text(p):
    return ''.join(p.xpath('.//w:t/text()', namespaces=ns))
paragraphs = body.findall('w:p', ns)
heading = next(p for p in paragraphs if text(p).startswith('5、FRAS'))
patterns = {'H1': deepcopy(paragraphs[142]), 'H2': deepcopy(paragraphs[18]), 'P': deepcopy(paragraphs[19])}
start = body.index(heading)
original_prefix = [E.tostring(item) for item in list(body)[:start]]
section = body.find('w:sectPr', ns)
section_bytes = E.tostring(section)
for item in list(body)[start:]:
    if item is not section:
        body.remove(item)

def elem(parent, tag, **attrs):
    item = E.SubElement(parent, W + tag)
    for key, val in attrs.items():
        item.set(W + key, str(val))
    return item

def prop(parent, tag, **attrs):
    for item in parent.findall('w:' + tag, ns):
        parent.remove(item)
    return elem(parent, tag, **attrs)

def paragraph(content, kind='P', page_break=False):
    p = deepcopy(patterns[kind])
    rp = p.find('w:r/w:rPr', ns)
    rp = deepcopy(rp) if rp is not None else E.Element(W + 'rPr')
    for item in list(p):
        if item.tag != W + 'pPr':
            p.remove(item)
    pp = p.find('w:pPr', ns)
    if pp is None:
        pp = E.Element(W + 'pPr')
        p.insert(0, pp)
    prop(pp, 'widowControl', val='1')
    if kind.startswith('H'):
        prop(pp, 'keepNext', val='1')
        prop(pp, 'outlineLvl', val='0' if kind == 'H1' else '1')
        prop(pp, 'spacing', before='180', after='100', line='360', lineRule='auto')
        prop(rp, 'color', val='000000')
    if page_break:
        prop(pp, 'pageBreakBefore', val='1')
    run = elem(p, 'r')
    run.append(rp)
    elem(run, 't').text = content
    body.insert(body.index(section), p)
    return p

new_heading = paragraph('5、界面与内容管理补充要求', 'H1', True)
paragraph('本章补充平台界面、管理操作、接口、文件存储和工程维护要求，用于指导详细设计、工程搭建及后续验收。前端采用 Next.js 与 React，后端采用 Rust、Salvo 和 Tokio，并使用 MySQL、SQLx 与 Redis；各模块沿用统一的权限、响应和持久化规则。')

paragraph('5.1、界面与管理操作', 'H2')
paragraph('公开页面与管理页面采用统一导航、配色、表单及列表样式，在窄屏下保持核心内容与操作可见。论坛和商品列表提供分页、筛选、排序、加载状态、空状态和可理解的错误提示；公开查询只展示允许访问且状态有效的内容。')
paragraph('管理中心按用户、板块、帖子、商品、举报、公告和任务划分页面，提供查看、编辑、处理及必要的图片上传。页面和组件按职责拆分，避免将全部管理业务集中在单个大型组件中。操作按钮按权限展示，后端仍须独立校验角色、板块授权和资源归属。')
paragraph('公告管理支持创建、编辑、删除、发布状态及发布时间维护；公开页面按有效发布状态和时间展示。普通用户、版主和管理员分别使用自己的授权范围，平台采用自主注册与登录，不接入校园 CAS。')

paragraph('5.2、接口与会话要求', 'H2')
paragraph('前端统一封装接口地址、请求超时、身份凭证及错误处理。响应包含结果、错误说明和业务数据，列表包含分页信息；公开查询与受保护操作按职责划分。创建、编辑、删除和状态修改须以服务端持久化结果作为成功依据。')
paragraph('后端按用户身份及角色授权，不因凭证有效就统一授予管理权限。账户封禁和会话撤销后，受保护请求与实时连接均须执行相应失效检查；浏览器清除凭证不能代替服务端会话失效机制。私聊、个人任务和受保护附件只向有权访问的对象开放。')

paragraph('5.3、文件与内容访问', 'H2')
paragraph('文件上传采用允许类型白名单，检查真实内容类型、图片解码结果、文件大小及数量配额；未知类型明确拒绝，不仅依赖上传请求声明的 Content-Type。采用不可预测的文件标识并校验存储路径，保存头像、帖子、商品与附件的归属关系。')
paragraph('公开文件与受保护文件采用各自的访问规则。上传失败不得留下可访问的不完整附件；删除、下架和权限变化时，应同步处理文件关联、内容查询、缓存及搜索索引。富文本和 Markdown 展示防止非预期脚本执行。')

paragraph('5.4、数据迁移与运行维护', 'H2')
paragraph('数据库结构通过版本化迁移管理，记录建表、字段调整、索引与必要初始化数据。用户、论坛、商品、会话、消息、通知、监控任务及治理记录使用各自业务模型；点赞收藏和任务匹配记录建立联合唯一约束，列表查询按用途设置索引及稳定分页。')
paragraph('本地与 Docker Compose 环境通过项目配置管理服务地址、数据库、缓存和文件目录，提供启动说明、健康检查及日志。密钥和账户初始配置独立管理，不将固定示例密码作为正式部署凭据；部署路径、备份恢复及清理范围须在运行说明中明确。')

paragraph('5.5、工程搭建与验收安排', 'H2')
paragraph('当前工作先统一需求、字段、权限和接口，再核验后端工程基础并跑通自主注册、登录、登出及当前用户查询。界面管理、完整文件上传和其他业务功能按后续任务逐步实现，各项完成声明应有实际运行和检查记录。')
paragraph('工程搭建后的验收覆盖前后端通信、权限拒绝、会话失效、服务重启和数据持久化；管理功能实现后检查分页、内容状态、上传类型、资源归属及操作审计。论坛互动、二手交易、实时私聊、AI 语义检索和周期监控分别按功能需求验收，避免仅凭页面或接口入口判断功能完成。')

relationships = E.fromstring(parts['word/_rels/document.xml.rels'])
removed_links = []
for relationship in list(relationships):
    if relationship.get('Type', '').endswith('/hyperlink') and 'FRAS-lab-website' in relationship.get('Target', ''):
        removed_links.append(relationship.get('Id'))
        relationships.remove(relationship)
    elif relationship.get('Id') == 'rIdFrasComments':
        relationship.set('Id', 'rIdReviewComments')

comments = E.fromstring(parts['word/comments.xml'])
review_comment = next(item for item in comments if item.get(W + 'id') == '7')
for item in list(review_comment):
    review_comment.remove(item)
cp = elem(review_comment, 'p')
cr = elem(cp, 'r')
elem(cr, 't').text = '本章整理为平台自身的界面与内容管理要求，保留必要功能和验收约定，移除外部来源名称、源码定位及链接。'
range_start = E.Element(W + 'commentRangeStart')
range_start.set(W + 'id', '7')
new_heading.insert(1, range_start)
elem(new_heading, 'commentRangeEnd', id='7')
comment_run = elem(new_heading, 'r')
elem(comment_run, 'commentReference', id='7')

def xml_bytes(item):
    return E.tostring(item, xml_declaration=True, encoding='UTF-8', standalone=True)
parts['word/document.xml'] = xml_bytes(document)
parts['word/_rels/document.xml.rels'] = xml_bytes(relationships)
parts['word/comments.xml'] = xml_bytes(comments)
assert [E.tostring(item) for item in list(body)[:start]] == original_prefix
assert E.tostring(section) == section_bytes
assert len(removed_links) == 10
for name, data in parts.items():
    if name.endswith(('.xml', '.rels')):
        E.fromstring(data)
        content = data.decode('utf-8').lower()
        for forbidden in ['fras', 'fraslab', '实验室网站', 'github.com', 'gygy-hh', '892e0b14d2a784c833597ecb9fc91f2a41b996d2']:
            assert forbidden not in content, (name, forbidden)
with ZipFile(draft, 'w') as archive:
    for info in infos:
        archive.writestr(info, parts[info.filename])
with ZipFile(baseline) as before, ZipFile(draft) as after:
    changed = [name for name in before.namelist() if before.read(name) != after.read(name)]
    assert set(changed) == {'word/document.xml', 'word/_rels/document.xml.rels', 'word/comments.xml'}
evidence = {
    'target': str(target), 'draft': str(draft), 'backup': str(baseline),
    'source_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(),
    'removed_source_links': len(removed_links), 'changed_parts': changed,
    'first_four_chapters_cover_styles_and_media_preserved': True,
    'all_xml_and_relationship_source_name_check': 'passed',
}
(work / 'structural-verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), 'utf-8')
print(json.dumps(evidence, ensure_ascii=False))
