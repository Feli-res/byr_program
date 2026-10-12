from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
import json, hashlib

root=Path(__file__).resolve().parent.parent
target=root/'北邮校园综合交互论坛_需求分析文档.docx'
work=root/'.requirements_work'
baseline=work/'before-submission-revision.docx'
baseline.write_bytes(target.read_bytes())
with ZipFile(target) as z:
    infos=z.infolist(); parts={i.filename:z.read(i.filename) for i in infos}
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
changes={
'（1）项目作为程序设计课程设计，采用模块化单体应用，按工程基础、论坛、二手交易、即时聊天、AI 匹配、定时监控、集成测试的顺序推进。具体开发期限和人员分工由课程安排确定。':
'（1）系统采用模块化单体结构，覆盖论坛交流、二手交易、即时聊天、AI 商品匹配和定时提醒。系统交付应完成核心功能、集成测试及需求规定中的验收流程；开发期限按课程安排执行。',
'（5）开发阶段使用本地文件存储，可按需要替换为对象存储。基础部署采用本地环境及 Docker Compose；官方认证、其他高校适配和大规模分布式部署作为后续扩展。':
'（5）系统以本地文件存储支持图片与附件，可按需要替换为对象存储。基础部署采用本地环境及 Docker Compose，能够独立运行核心论坛功能。',
'基础功能包括用户与权限、分区论坛、全局搜索、二手交易、一对一私聊、AI 商品匹配、周期监控与通知、管理治理。以下各项按输入、处理、输出和验收条件描述；功能要求为拟实现行为，不表示已经完成开发。':
'系统应提供用户与权限、分区论坛、全局搜索、二手交易、一对一私聊、AI 商品匹配、周期监控与通知、管理治理功能。各项功能的输入、处理、输出及验收条件规定如下。',
'容量应覆盖普通网页访问、并行发布评论、商品搜索、实时聊天及后台监控共同运行。基础演示至少包含两个分区和两个不同浏览器账户，验证帖子、商品、聊天、任务及通知的持久化；正式终端数、并行用户数、聊天连接数和数据规模尚未定量，须结合部署资源及压测确认后形成验收基线。':
'系统应支持网页访问、并行发布评论、商品搜索、实时聊天和后台监控共同运行。验收至少设置两个分区，并使用两个不同浏览器账户验证帖子、商品、聊天、任务和通知的持久化。终端数、并行用户数、聊天连接数及数据容量应形成统一验收指标，相关数值在第 4 章列为尚需解决的问题。',
'监控提醒的延迟由配置的检查周期、调度等待和处理时间组成，应记录下次计划时间与实际执行时间以便验证。监控不应每轮重复调用模型。普通请求、聊天、AI 和任务调度的具体响应时间阈值尚待压测确定，不作为已承诺性能数值。':
'监控提醒的延迟由配置的检查周期、调度等待和处理时间组成，应记录计划时间与实际执行时间以便验证。监控应复用已保存的筛选条件，避免每轮重复调用模型。普通请求、聊天、AI 解析和任务调度的响应时间指标应结合运行环境进行测试，具体阈值在第 4 章列为尚需解决的问题。',
'系统适应本地开发及容器化部署，通过配置调整数据库、缓存、服务地址和模型参数。后续可扩展官方认证、对象存储、语义检索及其他高校配置，但基础版本优先保持模块化单体结构。':
'系统应支持本地运行及容器化部署，通过配置调整数据库、缓存、服务地址和模型参数。官方认证、对象存储和语义检索接口应具备可扩展性，扩展时保持基础论坛、交易和消息功能的兼容性。',
'数据规模需按用户数、帖子评论数、商品数、消息数、任务数和附件量分别估算。预估总量可按“各类记录数量×平均记录大小＋附件总量＋索引、日志及备份开销”计算；增长量按周期新增记录和文件计入。当前数量、保存期限、文件配额和备份空间未定，须在容量基线确认后给出存储估算，不能将示例演示规模当作实际校园容量。':
'数据规模应按用户数、帖子评论数、商品数、消息数、任务数和附件量分别估算。预估总量按“各类记录数量×平均记录大小＋附件总量＋索引、日志及备份开销”计算，增长量按周期新增记录和文件计入。数据容量、保存期限、文件配额及备份空间应在部署前确定，并依据增长情况调整。',
'（7）课程实施：依据课程安排确定截止日期、人员分工和各阶段验收时间，优先完成论坛、交易、基础私聊、AI 匹配和定时通知闭环，再评估可选扩展。':
'（7）验收安排：确定功能验收、权限测试及异常恢复测试的时间和数据准备方式，覆盖论坛交流、商品发布、私聊、AI 匹配、监控及通知的完整使用流程。',
}
doc=E.fromstring(parts['word/document.xml'])
edited=[]
for p in doc.xpath('//w:body//w:p',namespaces=ns):
    nodes=p.xpath('.//w:t',namespaces=ns)
    text=''.join(n.text or '' for n in nodes)
    if text in changes:
        nodes[0].text=changes[text]
        for n in nodes[1:]:n.text=''
        edited.append(text)
assert len(edited)==len(changes),(len(edited),len(changes))
parts['word/document.xml']=E.tostring(doc,xml_declaration=True,encoding='UTF-8',standalone=True)
core=E.fromstring(parts['docProps/core.xml'])
for node in list(core):core.remove(node)
title=E.SubElement(core,'{http://purl.org/dc/elements/1.1/}title')
title.text='北邮校园综合交互论坛需求分析文档'
subject=E.SubElement(core,'{http://purl.org/dc/elements/1.1/}subject')
subject.text='程序设计实验课程需求分析'
parts['docProps/core.xml']=E.tostring(core,xml_declaration=True,encoding='UTF-8',standalone=True)
app=E.fromstring(parts['docProps/app.xml'])
for n in list(app):
    if E.QName(n).localname in ['Template','Words','Characters','Lines','Paragraphs','TotalTime','CharactersWithSpaces','Application','Company','Manager']:
        app.remove(n)
    elif E.QName(n).localname=='Pages':n.text='9'
parts['docProps/app.xml']=E.tostring(app,xml_declaration=True,encoding='UTF-8',standalone=True)
content='\n'.join(''.join(p.xpath('.//w:t/text()',namespaces=ns)) for p in doc.xpath('//w:body//w:p',namespaces=ns))
for word in ['github','hnu-doc','jhserver','gygy','Old_docs','湖南大学','YuQian Tang','刘瑞芳','其他高校','引用仓库','复用规划','不表示已经完成开发']:
    assert word.lower() not in content.lower(),word
for n,data in parts.items():
    if n.endswith('.xml') or n.endswith('.rels'):
        s=data.decode('utf-8')
        for word in ['YuQian Tang','刘瑞芳','github.com','hnu-doc','jhserver','gygy-hh','湖南大学']:
            assert word.lower() not in s.lower(),(n,word)
with ZipFile(target,'w') as z:
    for info in infos:z.writestr(info,parts[info.filename])
with ZipFile(baseline) as old,ZipFile(target) as new:
    changed=[n for n in old.namelist() if old.read(n)!=new.read(n)]
    assert set(changed)=={'word/document.xml','docProps/core.xml','docProps/app.xml'},changed
print(json.dumps({'edited_paragraphs':len(edited),'changed_parts':changed,'metadata_names_removed':True,'forbidden_content_check':'passed','target':str(target)},ensure_ascii=False))
