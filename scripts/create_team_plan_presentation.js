const path = require('path');
const fs = require('fs');
const Module = require('module');

// Use the PptxGenJS and JSZip copies already present in the machine's local pnpm store.
// No package is downloaded or installed by this script.
const LOCAL_PPTXGENJS = '/Users/wind/Library/pnpm/store/v11/files/46/962a757223c923d8bdb04f9937db36d4cc0c11fc502d16a64f92048cb8171a3cf26a144cc99d896db7aacfe8b576be7c474ae70a959b75d85242c49741c181';
const LOCAL_JSZIP = '/Users/wind/Library/pnpm/store/v11/files/93/fb52d512c60582bdf9318fefd958e9e76ecdd671abe70f3649c8adfcb42c60e62691f12aebfcca7088ea64b7af13c471cf5bb68de8c6599de9c478b368f0fa';
const originalModuleLoad = Module._load;
const cachedJSZip = require(LOCAL_JSZIP);
Module._load = function loadLocalDependency(request, parent, isMain) {
  if (request === 'jszip') return cachedJSZip;
  return originalModuleLoad.call(this, request, parent, isMain);
};
const PptxGenJS = require(LOCAL_PPTXGENJS);
Module._load = originalModuleLoad;

const pptx = new PptxGenJS();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = '可信医疗问答项目组';
pptx.company = '课程项目';
pptx.subject = '可信医疗问答系统四人分工与两个月计划';
pptx.title = '可信医疗问答系统：四人分工与两个月计划';
pptx.lang = 'zh-CN';
pptx.theme = {
  headFontFace: 'PingFang SC',
  bodyFontFace: 'PingFang SC',
  lang: 'zh-CN',
};
pptx.defineLayout({ name: 'WIDE', width: 13.333, height: 7.5 });
pptx.layout = 'WIDE';
pptx.margin = 0;

const OUT_DIR = path.join(__dirname, '..', 'output', 'pptx');
const OUT_FILE = path.join(OUT_DIR, '可信医疗问答系统_四人分工与两个月计划_汇报.pptx');
fs.mkdirSync(OUT_DIR, { recursive: true });

const C = {
  navy: '103C71',
  blue: '1F5FBF',
  sky: 'EAF2FF',
  pale: 'F6F9FD',
  text: '172033',
  muted: '5B6B82',
  line: 'D7E2F0',
  orange: 'F28C28',
  gold: 'FFF4DD',
  green: '2E7D5B',
  greenPale: 'EAF6F0',
  red: 'B5473C',
  redPale: 'FFF0ED',
  purple: '7756A8',
  purplePale: 'F3EEFB',
  white: 'FFFFFF',
};
const FONT = 'PingFang SC';
const W = 13.333;
const H = 7.5;

function addText(slide, text, x, y, w, h, opts = {}) {
  slide.addText(text, {
    x, y, w, h,
    fontFace: FONT,
    fontSize: opts.fontSize || 18,
    color: opts.color || C.text,
    bold: opts.bold || false,
    align: opts.align || 'left',
    valign: opts.valign || 'mid',
    margin: opts.margin ?? 0,
    breakLine: false,
    fit: 'shrink',
    paraSpaceAfterPt: 0,
    ...opts,
  });
}

function addRect(slide, x, y, w, h, fill, line = fill, radius = 0) {
  slide.addShape(radius ? pptx.ShapeType.roundRect : pptx.ShapeType.rect, {
    x, y, w, h,
    rectRadius: radius,
    fill: { color: fill },
    line: { color: line, transparency: line === fill ? 100 : 0, width: 0.5 },
  });
}

function addRule(slide, y, color = C.line) {
  slide.addShape(pptx.ShapeType.line, { x: 0.58, y, w: 12.18, h: 0, line: { color, width: 0.8 } });
}

function addFooter(slide, n) {
  addRule(slide, 7.12);
  addText(slide, '可信医疗问答系统｜四人分工与两个月计划', 0.6, 7.18, 5.8, 0.17, {
    fontSize: 7.5, color: C.muted,
  });
  addText(slide, String(n).padStart(2, '0'), 12.35, 7.16, 0.35, 0.18, {
    fontSize: 8, color: C.muted, align: 'right',
  });
}

function addTitle(slide, title, subtitle, n) {
  addText(slide, title, 0.62, 0.42, 10.9, 0.42, { fontSize: 25, bold: true, color: C.navy });
  if (subtitle) addText(slide, subtitle, 0.64, 0.91, 11.4, 0.25, { fontSize: 10, color: C.muted });
  slide.addShape(pptx.ShapeType.line, { x: 0.64, y: 1.26, w: 1.05, h: 0, line: { color: C.orange, width: 2.5 } });
  addFooter(slide, n);
}

function addLabel(slide, text, x, y, w, color) {
  addRect(slide, x, y, w, 0.31, color);
  addText(slide, text, x + 0.12, y + 0.03, w - 0.24, 0.2, { fontSize: 8.5, color: C.white, bold: true, align: 'center' });
}

function addFlowNode(slide, x, y, w, title, detail, fill, accent) {
  addRect(slide, x, y, w, 1.14, fill, fill, 0.05);
  slide.addShape(pptx.ShapeType.line, { x, y, w: 0, h: 1.14, line: { color: accent, width: 3 } });
  addText(slide, title, x + 0.17, y + 0.16, w - 0.3, 0.25, { fontSize: 13, bold: true, color: C.navy });
  addText(slide, detail, x + 0.17, y + 0.53, w - 0.28, 0.4, { fontSize: 8.7, color: C.muted, valign: 'top' });
}

function addArrow(slide, x1, y, x2) {
  slide.addShape(pptx.ShapeType.line, {
    x: x1, y, w: x2 - x1, h: 0,
    line: { color: C.blue, width: 1.2, beginArrowType: 'none', endArrowType: 'triangle' },
  });
}

// 1. Cover
{
  const slide = pptx.addSlide();
  slide.background = { color: C.white };
  addRect(slide, 0, 0, 13.333, 0.16, C.orange);
  addText(slide, '可信医疗问答系统', 0.75, 1.2, 7.6, 0.65, { fontSize: 34, bold: true, color: C.navy });
  addText(slide, '四人分工与两个月计划', 0.78, 1.98, 7.2, 0.4, { fontSize: 21, color: C.blue, bold: true });
  addText(slide, '课程项目汇报｜初学者版', 0.8, 2.54, 4.5, 0.25, { fontSize: 11, color: C.muted });
  addRule(slide, 3.1, C.line);
  addText(slide, '项目目标', 0.8, 3.45, 1.3, 0.25, { fontSize: 12, color: C.orange, bold: true });
  addText(slide, '从可靠医疗资料中找到原文，生成带出处的回答；资料不足时，明确提示无法可靠回答。', 0.8, 3.84, 6.3, 0.9, {
    fontSize: 19, color: C.text, bold: false, valign: 'top',
  });
  addText(slide, '仅用于课程和工程练习，不用于真实诊断、治疗或用药建议。', 0.8, 5.15, 5.9, 0.28, { fontSize: 10.5, color: C.red });
  addRect(slide, 8.4, 1.18, 3.9, 4.8, C.sky, C.sky, 0.1);
  addText(slide, '可信回答的四个要点', 8.75, 1.63, 3.2, 0.3, { fontSize: 15, bold: true, color: C.navy, align: 'center' });
  const coverItems = [
    ['可靠资料', '指南、共识、教材'],
    ['找到原文', '先检索再回答'],
    ['给出引用', '每个结论可回查'],
    ['必要时拒答', '资料不足不编造'],
  ];
  coverItems.forEach((item, i) => {
    const y = 2.22 + i * 0.83;
    addText(slide, String(i + 1).padStart(2, '0'), 8.76, y, 0.42, 0.25, { fontSize: 10, color: C.orange, bold: true });
    addText(slide, item[0], 9.24, y, 2.3, 0.23, { fontSize: 13, color: C.navy, bold: true });
    addText(slide, item[1], 9.24, y + 0.3, 2.4, 0.2, { fontSize: 9.5, color: C.muted });
  });
  addFooter(slide, 1);
}

// 2. Scope and process
{
  const slide = pptx.addSlide();
  addTitle(slide, '项目目标与使用边界', '系统的工作方式决定了每个人要交付什么', 2);
  addText(slide, '系统工作流程', 0.66, 1.55, 2.0, 0.28, { fontSize: 15, bold: true, color: C.navy });
  const xs = [0.66, 3.19, 5.72, 8.25, 10.78];
  const flow = [
    ['整理资料', '只纳入可追溯的指南、共识和教材', C.sky, C.blue],
    ['搜索原文', '关键词与语义搜索同时找相关段落', C.greenPale, C.green],
    ['生成回答', '模型只能根据已找到的原文回答', C.gold, C.orange],
    ['检查引用', '关键结论必须有原文支持', C.purplePale, C.purple],
    ['展示或拒答', '证据不足时解释无法可靠回答', C.redPale, C.red],
  ];
  flow.forEach((item, i) => {
    addFlowNode(slide, xs[i], 2.05, 1.85, item[0], item[1], item[2], item[3]);
    if (i < flow.length - 1) addArrow(slide, xs[i] + 1.89, 2.62, xs[i + 1] - 0.08);
  });
  addText(slide, '共同原则', 0.66, 4.1, 1.6, 0.28, { fontSize: 15, bold: true, color: C.navy });
  const principles = [
    ['不使用未授权资料', '成员 1 负责记录来源、版本和许可情况。'],
    ['不混入测试答案', '成员 4 负责让测试题与资料库保持隔离。'],
    ['不忽略失败案例', '四人每周共同抽查“原文、搜索结果、回答”是否对应。'],
  ];
  principles.forEach((item, i) => {
    const x = 0.66 + i * 4.18;
    addText(slide, `0${i + 1}`, x, 4.65, 0.32, 0.22, { fontSize: 10, color: C.orange, bold: true });
    addText(slide, item[0], x + 0.42, 4.63, 3.3, 0.23, { fontSize: 13, color: C.navy, bold: true });
    addText(slide, item[1], x + 0.42, 5.03, 3.35, 0.55, { fontSize: 10.5, color: C.muted, valign: 'top' });
  });
}

// 3. Beginner glossary
{
  const slide = pptx.addSlide();
  addTitle(slide, '初学者需要认识的五个模块', '先理解每个模块的作用，再开始分工', 3);
  const terms = [
    ['资料', '系统查阅的指南、专家共识和教材。'],
    ['分片', '把长文切成可搜索的小段，并保留原文位置。'],
    ['检索', '用户提问后，从资料中找最相关的小段。'],
    ['引用核验', '检查回答中的关键结论是否真的由原文支持。'],
    ['拒答', '资料不足、条件不清或证据冲突时，不给具体结论。'],
  ];
  terms.forEach((item, i) => {
    const y = 1.56 + i * 0.94;
    addRect(slide, 0.72, y, 2.28, 0.68, i % 2 ? C.pale : C.sky, i % 2 ? C.pale : C.sky, 0.04);
    addText(slide, item[0], 0.94, y + 0.18, 1.9, 0.22, { fontSize: 15, bold: true, color: C.navy, align: 'center' });
    addText(slide, item[1], 3.45, y + 0.1, 7.8, 0.43, { fontSize: 15, color: C.text, valign: 'mid' });
    addRule(slide, y + 0.72, C.line);
  });
  addRect(slide, 10.0, 1.55, 2.45, 4.72, C.gold, C.gold, 0.07);
  addText(slide, '推荐学习顺序', 10.23, 1.86, 1.95, 0.25, { fontSize: 14, bold: true, color: C.navy, align: 'center' });
  const learn = ['先看资料与原文', '再运行搜索功能', '最后学习回答、核验和拒答'];
  learn.forEach((item, i) => {
    addText(slide, String(i + 1), 10.24, 2.56 + i * 0.87, 0.3, 0.24, { fontSize: 11, color: C.orange, bold: true });
    addText(slide, item, 10.62, 2.47 + i * 0.87, 1.5, 0.48, { fontSize: 11, color: C.text, valign: 'mid' });
  });
}

// 4. Roles
{
  const slide = pptx.addSlide();
  addTitle(slide, '四人的分工', '每人有主责，也通过明确交接让其他成员可以继续工作', 4);
  const roles = [
    ['成员 1', '资料与质量', '整理可用医疗资料，记录来源和可靠性；切分长文，检查能否回到原文。', '交给团队：资料包、来源表、小段数据、抽检记录', C.blue, C.sky],
    ['成员 2', '搜索功能', '建立关键词与语义搜索，合并结果并把最相关的原文排在前面。', '交给团队：输入问题后返回相关原文的功能和搜索记录', C.green, C.greenPale],
    ['成员 3', '回答与可靠性', '让模型根据原文回答并标引用；判断关键句是否受原文支持；资料不足时拒答。', '交给团队：回答格式、引用规则、核验和拒答逻辑', C.orange, C.gold],
    ['成员 4', '测试与网页', '准备测试题，整合网页，保存实验结果，完成使用说明和演示材料。', '交给团队：测试题、结果表、可运行网页、汇报材料', C.purple, C.purplePale],
  ];
  roles.forEach((role, i) => {
    const y = 1.55 + i * 1.25;
    addRect(slide, 0.67, y, 12.0, 1.03, role[5], role[5], 0.03);
    addRect(slide, 0.67, y, 1.5, 1.03, role[4], role[4], 0.03);
    addText(slide, role[0], 0.84, y + 0.16, 1.16, 0.2, { fontSize: 10.5, bold: true, color: C.white, align: 'center' });
    addText(slide, role[1], 0.79, y + 0.49, 1.26, 0.22, { fontSize: 12, bold: true, color: C.white, align: 'center' });
    addText(slide, role[2], 2.45, y + 0.15, 5.85, 0.58, { fontSize: 12.3, color: C.text, valign: 'top' });
    addText(slide, role[3], 8.6, y + 0.16, 3.72, 0.56, { fontSize: 10.7, color: C.muted, valign: 'top' });
  });
  addText(slide, '分工不是流水线：第 2 周起，成员 3 和成员 4 就可用小样本并行开发，不必等待全部资料准备完成。', 0.72, 6.55, 11.9, 0.27, { fontSize: 11.5, color: C.red, bold: true, align: 'center' });
}

function addPhaseSlide(n, title, subtitle, weeks, phaseNote) {
  const slide = pptx.addSlide();
  addTitle(slide, title, subtitle, n);
  const left = 0.66;
  const totalW = 12.0;
  const gap = 0.18;
  const cardW = (totalW - 3 * gap) / 4;
  weeks.forEach((week, i) => {
    const x = left + i * (cardW + gap);
    addLabel(slide, `第 ${week.week} 周`, x, 1.55, cardW, i % 2 ? C.blue : C.navy);
    addText(slide, week.name, x, 2.0, cardW, 0.34, { fontSize: 16, bold: true, color: C.navy, align: 'center' });
    addRule(slide, 2.47, C.line);
    week.items.forEach((item, index) => {
      addText(slide, `0${index + 1}`, x + 0.06, 2.77 + index * 0.78, 0.27, 0.18, { fontSize: 8.5, bold: true, color: C.orange });
      addText(slide, item, x + 0.4, 2.69 + index * 0.78, cardW - 0.42, 0.55, { fontSize: 10.6, color: C.text, valign: 'top' });
    });
    addRect(slide, x, 5.65, cardW, 0.72, C.pale, C.pale, 0.04);
    addText(slide, '本周检查', x + 0.1, 5.75, cardW - 0.2, 0.15, { fontSize: 8, bold: true, color: C.blue, align: 'center' });
    addText(slide, week.check, x + 0.12, 5.98, cardW - 0.24, 0.23, { fontSize: 9.1, color: C.muted, align: 'center', valign: 'mid' });
  });
  addText(slide, phaseNote, 0.75, 6.62, 11.85, 0.2, { fontSize: 10.8, color: C.muted, align: 'center' });
}

// 5. Weeks 1-4
addPhaseSlide(5, '第 1-4 周：搭建可运行的基础版本', '资料、搜索、回答和评测同步开始', [
  { week: 1, name: '范围与准备', items: ['成员 1 选主题和资料来源', '成员 2 安装环境并定义搜索结果', '成员 3 确定回答和引用模板', '成员 4 设计测试题模板'], check: '全组跑通最小示例' },
  { week: 2, name: '首批样本', items: ['成员 1 切分首批资料', '成员 2 做两种搜索初版', '成员 3 用原文生成带引用回答', '成员 4 写 20-30 道测试题'], check: '首批资料可回答问题' },
  { week: 3, name: '打通流程', items: ['成员 1 检查表格、剂量和禁忌', '成员 2 合并两种搜索结果', '成员 3 接入搜索结果并记录引用', '成员 4 自动保存测试结果'], check: '完成端到端流程' },
  { week: 4, name: '初步优化', items: ['成员 1 抽检低质量小段', '成员 2 加入二次排序和上下文', '成员 3 准备引用支持判断样例', '成员 4 比较搜索方案并搭网页'], check: '确认可靠的搜索组合' },
], '第 4 周结束时，团队应能演示“提问、找原文、生成回答、查看引用”的完整流程。');

// 6. Weeks 5-8
addPhaseSlide(6, '第 5-8 周：补齐可信度与完成交付', '从可运行原型走向可复现的课程项目成果', [
  { week: 5, name: '引用核验', items: ['成员 1 根据错误修复资料', '成员 2 调整搜索数量和排序', '成员 3 删除或改写无证据关键句', '成员 4 把原文和引用显示在网页'], check: '人工抽查引用是否正确' },
  { week: 6, name: '拒答与稳定性', items: ['成员 1 整理来源和许可说明', '成员 2 检查搜索稳定性', '成员 3 校准资料不足时的拒答', '成员 4 完善上传、会话和部署'], check: '可答与不可答均能处理' },
  { week: 7, name: '全量测试', items: ['成员 1 复核失败题关联资料', '成员 2 修复搜不到或搜错问题', '成员 3 修复引用和拒答问题', '成员 4 跑完全部对比测试'], check: '每人均可复现结果' },
  { week: 8, name: '汇报交付', items: ['成员 1 整理资料说明和质量记录', '成员 2 整理搜索构建说明', '成员 3 完成人工核验结论', '成员 4 完成演示、报告和答辩材料'], check: '完成演示彩排和归档' },
], '第 7 周后尽量固定测试题、搜索参数和回答模板，避免最后阶段改变基准。');

// 7. Weekly collaboration
{
  const slide = pptx.addSlide();
  addTitle(slide, '每周协作方式', '用固定节奏减少等待，尽早发现资料、搜索和回答之间的问题', 7);
  const steps = [
    ['周初', '明确本周交付', '在共享任务表写清要交什么；遇到术语先确认含义。', C.sky, C.blue],
    ['周中', '交付小样本', '成员 1 提供资料样本，成员 2 提供简版搜索，成员 3、4 立即接入。', C.greenPale, C.green],
    ['周末', '固定小题联调', '用 10-20 道题检查原文、搜索、回答和引用，记录失败原因。', C.gold, C.orange],
  ];
  steps.forEach((step, i) => {
    const y = 1.56 + i * 1.5;
    addRect(slide, 0.72, y, 11.9, 1.12, step[3], step[3], 0.05);
    addRect(slide, 0.72, y, 1.56, 1.12, step[4], step[4], 0.05);
    addText(slide, step[0], 0.92, y + 0.34, 1.15, 0.24, { fontSize: 16, bold: true, color: C.white, align: 'center' });
    addText(slide, step[1], 2.68, y + 0.19, 2.3, 0.25, { fontSize: 15, bold: true, color: C.navy });
    addText(slide, step[2], 5.05, y + 0.18, 6.85, 0.52, { fontSize: 13, color: C.text, valign: 'mid' });
  });
  addText(slide, '固定记录四件事', 0.75, 6.05, 1.6, 0.22, { fontSize: 14, bold: true, color: C.navy });
  const metrics = ['找到了什么原文', '回答写了什么', '引用是否支持结论', '哪里失败、谁负责修复'];
  metrics.forEach((metric, i) => {
    const x = 2.32 + i * 2.47;
    addText(slide, String(i + 1), x, 6.05, 0.24, 0.2, { fontSize: 10, bold: true, color: C.orange, align: 'center' });
    addText(slide, metric, x + 0.32, 6.02, 2.05, 0.25, { fontSize: 10.5, color: C.text, align: 'center' });
  });
}

// 8. Deliverables
{
  const slide = pptx.addSlide();
  addTitle(slide, '最终交付', '第 8 周结束时，团队应能展示系统、说明证据来源，并复现实验结果', 8);
  const deliverables = [
    ['可运行的问答网页', '输入中文问题后，展示回答和相关原文。'],
    ['可回查的引用', '每个关键结论都能查看对应的原文和出处。'],
    ['明确的拒答提示', '资料不足时，系统解释无法可靠回答。'],
    ['可重复的测试结果', '同一份资料、配置和测试题能再次运行并得到同类结果。'],
    ['完整的项目材料', '资料说明、部署指南、实验报告和答辩材料。'],
  ];
  deliverables.forEach((item, i) => {
    const y = 1.55 + i * 0.83;
    addText(slide, String(i + 1).padStart(2, '0'), 0.78, y + 0.11, 0.36, 0.18, { fontSize: 10, color: C.orange, bold: true });
    addText(slide, item[0], 1.28, y + 0.03, 2.65, 0.27, { fontSize: 15, bold: true, color: C.navy });
    addText(slide, item[1], 4.1, y + 0.03, 7.65, 0.29, { fontSize: 13, color: C.text });
    addRule(slide, y + 0.53, C.line);
  });
  addRect(slide, 0.75, 6.1, 11.82, 0.63, C.navy, C.navy, 0.05);
  addText(slide, '汇报时重点展示：一次真实提问、检索到的原文、带引用的回答，以及资料不足时的拒答。', 1.0, 6.28, 11.3, 0.18, { fontSize: 12.5, color: C.white, bold: true, align: 'center' });
}

pptx.writeFile({ fileName: OUT_FILE });
console.log(OUT_FILE);
