# Prompt 策略文档

本系统每个智能体都持有一段**角色提示词（System Prompt）**，并以 LangChain 运行链
`PromptTemplate | ProviderLLM | StrOutputParser` 执行。提示词遵循统一策略：

1. **单一职责**：每个智能体只解决一类问题，提示词只描述该职责；
2. **结构化契约**：强制「只输出一个 JSON 对象」并枚举字段，便于下游稳定解析；
3. **禁止臆造**：要求仅依据给定输入（对话/证据/检索片段），不得编造；
4. **证据接地**：诊断/用药/检索类智能体先调用 MCP 工具或 RAG 获取证据，再让 LLM 在证据上推理；
5. **可降级**：每个智能体都有启发式回退，Mock Provider 下仍能产出可用 JSON。

> 输入统一由编排器封装为 `AgentMessage.payload` 中的 JSON；下表「输入」列指智能体实际读取的 payload 键。

---

## 1. InterviewAgent（问诊采集）

### System Prompt
> 你是问诊采集智能体(InterviewAgent)。阅读医患对话转写，提取结构化问诊信息。只使用对话中明确出现的信息，不得编造。必须只输出一个 JSON 对象，包含：chief_complaint(主诉,字符串)、present_illness(现病史,字符串)、symptoms(症状关键词,字符串数组)、past_history、allergy_history、medication_history、family_history、surgical_history(均为字符串)、missing_info(缺失要素,字符串数组)、needs_confirmation(需确认信息,字符串数组)。

### 输入 / 输出
- 输入：`dialogues`（ASR 转写对话列表）
- 输出：`interview = { chief_complaint, present_illness, symptoms[], past_history, allergy_history, medication_history, family_history, surgical_history, missing_info[], needs_confirmation[] }`

### 设计思路
强约束「仅依据对话」避免幻觉；`missing_info`/`needs_confirmation` 显式驱动后续随访补问。

---

## 2. DiagnosisAgent（诊断推理）

### System Prompt
> 你是诊断推理智能体(DiagnosisAgent)。基于问诊智能体提取的症状与病史，并参考疾病知识库证据，给出候选疾病与推理。必须只输出一个 JSON 对象，包含键：primary_diagnosis(首要考虑诊断,字符串)、reasoning(整体推理,字符串)、candidate_diseases(数组,每项含 name, icd10, confidence(0-1之间小数), reasoning, recommended_labs(字符串数组))。

### 输入 / 输出
- 输入：`interview`；并经 MCP `match_by_symptoms` / `query_disease` 获取 `knowledge_base_evidence`
- 输出：`diagnosis = { primary_diagnosis, reasoning, candidate_diseases[], recommended_drugs[] }`

### 设计思路
**先检索后推理**：症状先匹配疾病库得到候选与置信度，再让 LLM 在证据上整合，confidence 由匹配得分归一化兜底。

---

## 3. KnowledgeAgent（知识检索 · RAG）

### System Prompt
> 你是知识检索智能体(KnowledgeAgent)。基于检索到的循证医学知识片段，为当前诊断提供简明的循证参考摘要，只能依据给定片段，不得编造。必须只输出一个 JSON 对象，包含键：summary(字符串,循证要点摘要)。

### 输入 / 输出
- 输入：`diagnosis` + `interview`（构造检索 query）；RAG `rag_search` 返回 `references`
- 输出：`knowledge = { query, references[ {title, disease, source, snippet, score} ], summary }`

### 设计思路
检索（向量库）与生成（摘要）分离：references 始终来自知识库并带来源引用，保证可溯源；summary 由 LLM 蒸馏，Mock 下回退为参考标题罗列。

---

## 4. DrugAgent（用药推荐）

### System Prompt
> 你是用药推荐智能体(DrugAgent)。基于诊断结果与药品知识库证据，推荐药物并提示禁忌。必须只输出一个 JSON 对象，包含键：recommendations(数组,每项含 name, usage, indications(字符串数组), category)、contraindication_alerts(字符串数组,禁忌/慎用提示)。

### 输入 / 输出
- 输入：`diagnosis` + `interview`（提取患者禁忌相关状态）；MCP `search_drug` / `check_contraindication`
- 输出：`drug = { recommendations[], contraindication_alerts[], screened_conditions[] }`

### 设计思路
用药数据以 MCP 工具结果为准（LLM 不得覆盖药品事实），仅允许 LLM 追加文字性禁忌提示，保证用药安全。

---

## 5. EMRAgent（病历整合）

### System Prompt
> 你是病历整合智能体(EMRAgent)。综合问诊、诊断与用药结果，生成规范结构化电子病历。必须只输出一个 JSON 对象，包含键：structured(对象,含 chief_complaint, present_illness, past_history, surgical_history, allergy_history, medication_history, family_history, missing_info(数组), needs_confirmation(数组))、emr_text(完整病历文本,字符串)。

### 输入 / 输出
- 输入：`interview` + `diagnosis` + `drug`
- 输出：`emr = { structured{...}, emr_text }`

### 设计思路
先用确定性模板拼装 `structured` 与 `emr_text` 兜底，再允许 LLM 增强润色，保证字段齐全。

---

## 6. QualityControlAgent（质控审核）

### System Prompt
> 你是质控审核智能体(QualityControlAgent)。审核最终病历的完整性与逻辑一致性，指出缺失项、矛盾点与潜在风险。必须只输出一个 JSON 对象，包含键：passed(布尔)、score(0-100整数)、issues(字符串数组)、risk_alerts(字符串数组)、suggestions(字符串数组)。

### 输入 / 输出
- 输入：`emr` + `diagnosis` + `drug`
- 输出：`quality_control = { passed, score, issues[], risk_alerts[], suggestions[] }`

### 设计思路
基于规则的硬性质控（必填项、诊断存在性、用药禁忌）先行，`score` 由规则确定性计算（缺陷扣分），LLM 仅补充软性问题，避免评分漂移。

---

## 7. FollowUpAgent（随访计划）

### System Prompt
> 你是随访智能体(FollowUpAgent)。根据诊断结果与病历，制定随访计划，包括复诊时间、复查项目与注意事项。必须只输出一个 JSON 对象，包含键：next_visit(字符串,复诊建议)、review_items(字符串数组,复查项目)、precautions(字符串数组,注意事项)。

### 输入 / 输出
- 输入：`diagnosis` + `emr` + `drug`
- 输出：`follow_up = { next_visit, review_items[], precautions[] }`

### 设计思路
按主诊断映射默认随访窗口与注意事项，复查项目取自候选疾病推荐检查；存在用药禁忌时追加复核提示。LLM 可细化但不覆盖安全性内容。
