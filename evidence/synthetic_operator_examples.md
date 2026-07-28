# Worked synthetic before/after perturbation examples

These examples use one script-generated synthetic seed (`mock_001`) and disclose the exact archived text changes. The perturbation step does not read or inject real-record input.

- Original source: `data/mock_cases_80/模拟病历1.md`
- Original SHA256: `fbf08814d6149837fb8f1681181b10452d6619491a77d16413a61257cf04679c`

## H1

- Variant source: `data/perturb_cases_600/mock_001_H1.md`
- Variant SHA256: `7e7a02b7b06be8e3f4b63b4e73e48f7fc57efd2013b4bfe568e741a616319672`

```diff
--- mock_001_original
+++ mock_001_H1
@@ -3,11 +3,11 @@
 年龄:47岁
 科别:胃肠外科门诊
 主诉:反酸烧心伴进食不适1月余
-现病史:2025-08-24胃镜：距门齿38.8cm处EGJ/贲门可见环周不规则溃疡隆起型肿物，管腔轻度狭窄，可见接触性出血。定位：肿瘤中心距齿状线/ Z线Z线上4.4cm，Siewert I型。活检病理：高分化腺癌。免疫组化/分子：HER2(0)；MMR(pMMR)；MSI(MSS)；PD-L1 CPS 2。2025-09-14增强CT：食管下段及贲门壁不规则增厚，邻近淋巴结肿大；临床分期：cT3-4N+M0，III期。PET-CT：未见明确远处转移。
+现病史:2025-08-24胃镜：距门齿38.8cm处EGJ/贲门可见环周不规则溃疡隆起型肿物，管腔轻度狭窄，可见接触性出血。定位：肿瘤中心距齿状线/ Z线Z线上4.4cm，Siewert I型。MMR(pMMR)；MSI(MSS)；PD-L1 CPS 2。2025-09-14增强CT：食管下段及贲门壁不规则增厚，邻近淋巴结肿大；临床分期：cT3-4N+M0，III期。PET-CT：未见明确远处转移。
 既往史:2型糖尿病
 过敏史:否认过敏史
 个人史:无特殊
 家族史:否认肿瘤家族史
 体格检查:无特殊
-辅助检查:见现病史
-诊断:Siewert I型胃食管结合部腺癌（C15）；临床分期III期
+辅助检查:见现病史；病理/活检：未提供组织学类型
+诊断:Siewert I型胃食管结合部癌（C15）；临床分期III期
```

## H2

- Variant source: `data/perturb_cases_600/mock_001_H2.md`
- Variant SHA256: `ab2d17585d1c1331056231f784aa3efc1c9f7df8bfc93cf5db6e1f4bb6c3212e`

```diff
--- mock_001_original
+++ mock_001_H2
@@ -3,11 +3,11 @@
 年龄:47岁
 科别:胃肠外科门诊
 主诉:反酸烧心伴进食不适1月余
-现病史:2025-08-24胃镜：距门齿38.8cm处EGJ/贲门可见环周不规则溃疡隆起型肿物，管腔轻度狭窄，可见接触性出血。定位：肿瘤中心距齿状线/ Z线Z线上4.4cm，Siewert I型。活检病理：高分化腺癌。免疫组化/分子：HER2(0)；MMR(pMMR)；MSI(MSS)；PD-L1 CPS 2。2025-09-14增强CT：食管下段及贲门壁不规则增厚，邻近淋巴结肿大；临床分期：cT3-4N+M0，III期。PET-CT：未见明确远处转移。
+现病史:2025-08-24活检病理：高分化腺癌。免疫组化/分子：HER2(0)；MMR(pMMR)；MSI(MSS)；PD-L1 CPS 2。2025-09-14增强CT：食管下段及贲门壁不规则增厚，邻近淋巴结肿大；临床分期：cT3-4N+M0，III期。PET-CT：未见明确远处转移。
 既往史:2型糖尿病
 过敏史:否认过敏史
 个人史:无特殊
 家族史:否认肿瘤家族史
 体格检查:无特殊
-辅助检查:见现病史
+辅助检查:见现病史；已行胃镜检查，但病历未记录任何所见/结果细节
 诊断:Siewert I型胃食管结合部腺癌（C15）；临床分期III期
```

## H3

- Variant source: `data/perturb_cases_600/mock_001_H3.md`
- Variant SHA256: `cdf6d2ef8b91f04ad6bea323eabe6a23ee54adc81e29ff416ccb4c0a27f5adc9`

```diff
--- mock_001_original
+++ mock_001_H3
@@ -9,5 +9,5 @@
 个人史:无特殊
 家族史:否认肿瘤家族史
 体格检查:无特殊
-辅助检查:见现病史
-诊断:Siewert I型胃食管结合部腺癌（C15）；临床分期III期
+辅助检查:见现病史；增强CT提示肝脏多发转移（M1）
+诊断:Siewert I型胃食管结合部腺癌（C15）
```

## H4

- Variant source: `data/perturb_cases_600/mock_001_H4.md`
- Variant SHA256: `ee770b085e78b345d7684a318f83359f0438f0309ce7766d25d7cd29db6cc61d`

```diff
--- mock_001_original
+++ mock_001_H4
@@ -3,11 +3,11 @@
 年龄:47岁
 科别:胃肠外科门诊
 主诉:反酸烧心伴进食不适1月余
-现病史:2025-08-24胃镜：距门齿38.8cm处EGJ/贲门可见环周不规则溃疡隆起型肿物，管腔轻度狭窄，可见接触性出血。定位：肿瘤中心距齿状线/ Z线Z线上4.4cm，Siewert I型。活检病理：高分化腺癌。免疫组化/分子：HER2(0)；MMR(pMMR)；MSI(MSS)；PD-L1 CPS 2。2025-09-14增强CT：食管下段及贲门壁不规则增厚，邻近淋巴结肿大；临床分期：cT3-4N+M0，III期。PET-CT：未见明确远处转移。
+现病史:2025-08-24胃镜：距门齿38.8cm处EGJ/贲门可见环周不规则溃疡隆起型肿物，管腔轻度狭窄，可见接触性出血。定位：活检病理：高分化腺癌。免疫组化/分子：HER2(0)；MMR(pMMR)；MSI(MSS)；PD-L1 CPS 2。2025-09-14增强CT：食管下段及贲门壁不规则增厚，邻近淋巴结肿大；临床分期：cT3-4N+M0，III期。PET-CT：未见明确远处转移。
 既往史:2型糖尿病
 过敏史:否认过敏史
 个人史:无特殊
 家族史:否认肿瘤家族史
 体格检查:无特殊
 辅助检查:见现病史
-诊断:Siewert I型胃食管结合部腺癌（C15）；临床分期III期
+诊断:Siewert I型胃食管结合部腺癌（C15）
```

## H5

- Variant source: `data/perturb_cases_600/mock_001_H5.md`
- Variant SHA256: `659478436fa904d8df8d064655d540b76e9dce10cf06781e00b784e0354b8452`

```diff
--- mock_001_original
+++ mock_001_H5
@@ -3,11 +3,11 @@
 年龄:47岁
 科别:胃肠外科门诊
 主诉:反酸烧心伴进食不适1月余
-现病史:2025-08-24胃镜：距门齿38.8cm处EGJ/贲门可见环周不规则溃疡隆起型肿物，管腔轻度狭窄，可见接触性出血。定位：肿瘤中心距齿状线/ Z线Z线上4.4cm，Siewert I型。活检病理：高分化腺癌。免疫组化/分子：HER2(0)；MMR(pMMR)；MSI(MSS)；PD-L1 CPS 2。2025-09-14增强CT：食管下段及贲门壁不规则增厚，邻近淋巴结肿大；临床分期：cT3-4N+M0，III期。PET-CT：未见明确远处转移。
+现病史:2025-08-24胃镜：距门齿38.8cm处EGJ/贲门可见环周不规则溃疡隆起型肿物，管腔轻度狭窄，可见接触性出血。定位：活检病理：高分化腺癌。免疫组化/分子：HER2(0)；MMR(pMMR)；MSI(MSS)；PD-L1 CPS 2。2025-09-14增强CT：食管下段及贲门壁不规则增厚，邻近淋巴结肿大；临床分期：cT3-4N+M0，III期。PET-CT：未见明确远处转移。
 既往史:2型糖尿病
 过敏史:否认过敏史
 个人史:无特殊
 家族史:否认肿瘤家族史
 体格检查:无特殊
-辅助检查:见现病史
-诊断:Siewert I型胃食管结合部腺癌（C15）；临床分期III期
+辅助检查:见现病史；定位：肿瘤中心距齿状线/Z线 Z线下6.0cm
+诊断:Siewert I型胃食管结合部腺癌（C15）
```

## H6

- Variant source: `data/perturb_cases_600/mock_001_H6.md`
- Variant SHA256: `a6803549cbe4439adc6d71df3a5e5720cb73f1a6ab52ff55b83bcc74d2a91a3b`

```diff
--- mock_001_original
+++ mock_001_H6
@@ -5,7 +5,6 @@
 主诉:反酸烧心伴进食不适1月余
 现病史:2025-08-24胃镜：距门齿38.8cm处EGJ/贲门可见环周不规则溃疡隆起型肿物，管腔轻度狭窄，可见接触性出血。定位：肿瘤中心距齿状线/ Z线Z线上4.4cm，Siewert I型。活检病理：高分化腺癌。免疫组化/分子：HER2(0)；MMR(pMMR)；MSI(MSS)；PD-L1 CPS 2。2025-09-14增强CT：食管下段及贲门壁不规则增厚，邻近淋巴结肿大；临床分期：cT3-4N+M0，III期。PET-CT：未见明确远处转移。
 既往史:2型糖尿病
-过敏史:否认过敏史
 个人史:无特殊
 家族史:否认肿瘤家族史
 体格检查:无特殊
```
