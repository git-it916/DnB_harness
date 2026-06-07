"""골든셋 확장 + 케이스별 검증 (GOLDENSET.md §3/§4/§5 준수).

무할루시네이션 원칙:
- contract_raw 는 PM 확정본(C001~C030)에 이미 존재하는 문자열만 재사용(출처 대조).
- 수치/날짜/기간/불리언 케이스는 실제 프로젝트 파서로 재계산해 gold_label 정합성 검증.
- 합성(IM 원본에 없는 표기)은 note 에 명시.

실행: python scripts/expand_golden.py        # 검증만(드라이런)
      python scripts/expand_golden.py --write # 검증 통과 시 CSV 기록
"""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

from src.canonical.compare import compare_values
from src.canonical.parsers import (
    parse_date,
    parse_duration_months,
    parse_percent,
)
from src.canonical.policy import load_field_policies
from src.pipelines.cross_check import FIELD_LABELS
from src.scoring.golden import load_golden_master

POLICIES = load_field_policies()

CSV_PATH = Path("tests/golden/golden_master.csv")
INCEPTION = date(2025, 7, 22)
MATURITY_TARGET = "2027-07-22"

FEE_RANGE = {
    "fee_schedule.management_fee": (0.0, 5.0),
    "fee_schedule.trust_fee": (0.0, 2.0),
    "fee_schedule.sales_fee": (0.0, 3.0),
    "redemption_terms.redemption_fee": (0.0, 100.0),
}
def _last_day(y: int, m: int) -> int:
    if m == 12:
        return 31
    return (date(y, m + 1, 1) - date(y, m, 1)).days


def add_months(d: date, months: int) -> date:
    total = (d.month - 1) + months
    y = d.year + total // 12
    m = total % 12 + 1
    day = min(d.day, _last_day(y, m))
    return date(y, m, day)


# --- 신규 케이스 정의 -------------------------------------------------------
# (id, category, field, label, gold, mut, diff, anchor_id, im, im_page, signal, pitfall, note)
# anchor_id: contract_raw 를 가져올 기존 case_id. '' 면 contract 공란(한쪽 부재).
NEW = [
    # fund.name
    ("C031","정상","fund.name","펀드명(전각)","match","format_diff","easy","C001","이지스블랙ＯＮ 일반사모투자신탁제１호",9,"normalization","전각 영문/숫자(ＯＮ,１)를 다른 문자로 인식","합성 — 전각 정규화 테스트"),
    ("C032","변조","fund.name","펀드명(상품라인 혼동)","mismatch","char_typo","hard","C002","이지스밸류ON 일반사모투자신탁제1호",9,"cross_check+llm_judge","동일 운용사의 다른 상품라인(블랙→밸류)을 같은 펀드로 오인","블랙ON↔밸류ON 혼동"),
    ("C033","정상","fund.name","펀드명(괄호 부기)","match","semantic_equivalent","medium","C002","이지스블랙ON 일반사모투자신탁제1호(전문투자형)",9,"llm_judge","괄호 부기(전문투자형)를 다른 펀드로 분리","핵심 명칭 동일·부기만 추가. 합성"),
    ("C063","정상","fund.name","펀드명(공백 전제거)","match","whitespace_normalize","easy","C001","이지스블랙ON일반사모투자신탁제1호",9,"normalization","공백 완전 제거를 다른 펀드로 오인","공백 전(全) 제거"),
    # fund.type
    ("C034","변조","fund.type","펀드유형(개방형 반전)","mismatch","bool_flip","hard","C003","일반사모집합투자기구, 투자신탁형, 혼합자산형, 단위형, 개방형, 사모형",9,"llm_judge","유형목록 속 폐쇄형→개방형 반전을 놓침(환매구조 핵심)","폐쇄형→개방형 단일 치환"),
    ("C035","변조","fund.type","펀드유형(자산유형 교체)","mismatch","entity_swap","medium","C003","일반사모집합투자기구, 투자신탁형, 증권형, 단위형, 폐쇄형, 사모형",9,"llm_judge","자산유형(혼합자산형→증권형)을 순서차로 오인","혼합자산형→증권형"),
    ("C036","변조","fund.type","펀드유형(공모 반전)","mismatch","bool_flip","hard","C003","일반사모집합투자기구, 투자신탁형, 혼합자산형, 단위형, 폐쇄형, 공모형",9,"llm_judge","사모→공모 반전(모집방식 규제구분)을 놓침","사모형→공모형"),
    # fund.inception_date
    ("C037","정상","fund.inception_date","설정일(점 구분)","match","format_diff","easy","C004","펀드설정일(예정) 2025.07.22",9,"normalization","점 구분 날짜를 하이픈과 다른 표기로 오인","2025.07.22=2025-07-22"),
    ("C038","변조","fund.inception_date","설정일(연도 시프트)","mismatch","date_shift","hard","C004","펀드설정일(예정) 2024년7월22일",9,"cross_check","연도 1년(2025→2024) 차이를 표기차로 오인","정답 2025 vs 변조 2024"),
    ("C039","변조","fund.inception_date","설정일(월 시프트)","mismatch","date_shift","medium","C004","펀드설정일(예정) 2025년8월22일",9,"cross_check","월(7→8) 차이를 놓침","정답 7월 vs 변조 8월"),
    # fund.maturity_date
    ("C040","정상","fund.maturity_date","만기일(24개월 동치)","match","unit_conversion","medium","C006","펀드만기 24개월 (수익자 동의 하에 조기청산 가능)",9,"normalization","24개월=2년 환산 누락","설정일+24개월=2027-07-22"),
    ("C041","변조","fund.maturity_date","만기일(25개월)","mismatch","date_shift","hard","C006","펀드만기 25개월",9,"llm_judge","25개월을 2년으로 반올림해 합격","24개월(정답) vs 25개월"),
    ("C042","변조","fund.maturity_date","만기일(1일 시프트)","mismatch","date_shift","hard","C006","만기 2027년 7월 21일",9,"cross_check","만기 1일(22→21) 차이를 놓침","정답 2027-07-22 vs 2027-07-21"),
    ("C065","변조","fund.maturity_date","만기일(1년)","mismatch","date_shift","medium","C006","펀드만기 1년",9,"llm_judge","만기 절반(1년)을 2년으로 오인","12개월(변조) vs 24개월"),
    # party.asset_manager
    ("C043","정상","party.asset_manager","운용사(법인격 생략)","match","format_diff","easy","C008","이지스자산운용",24,"normalization","법인격(주식회사) 생략을 다른 회사로 오인","법인격 생략"),
    ("C044","변조","party.asset_manager","운용사(엔티티 교체)","mismatch","entity_swap","medium","C024","집합투자업자 미래에셋자산운용 주식회사",24,"cross_check","운용사 완전교체를 회사명 존재만으로 합격","이지스→미래에셋"),
    ("C069","변조","party.asset_manager","운용사(운용→운영)","mismatch","char_typo","hard","C024","집합투자업자 이지스자산운영",24,"cross_check+llm_judge","'운용→운영' 1글자 오기를 OCR노이즈로 오인","C007과 달리 실제 오기. 합성 IM"),
    # party.trustee
    ("C045","변조","party.trustee","신탁업자(증→즈)","mismatch","char_typo","hard","C009","신탁업자 엔에이치투자즈권 주식회사",24,"cross_check+llm_judge","'증→즈' 1글자 차이를 OCR노이즈로 오인","엔에이치투자증권 vs 투자즈권. 합성 IM"),
    ("C046","변조","party.trustee","신탁업자(가짜 인용)","mismatch","fake_citation","hard","C009","신탁업자 엔에이치투자증권 주식회사",999,"g2_citation","값이 맞으니 페이지 검증없이 합격","합성 — 가짜 인용(999). G2 출처 가드 전용"),
    # party.distributor
    ("C047","변조","party.distributor","판매사(환각 신설)","mismatch","invent_clause","medium","","판매회사 삼성증권 주식회사",24,"cross_check","계약서에 없는 판매사를 IM이 신설해도 합격","계약서 판매사 부재인데 IM 일방 신설. 라벨 논의 — PM 확정. 합성"),
    # fee management
    ("C048","변조","fee_schedule.management_fee","운용보수(자릿수 과소)","mismatch","decimal_shift","hard","C011","[운용] 연[ 0.089 ] %",9,"normalization+cross_check","0.89 vs 0.089 자릿수 함정(과소보수)","10배 과소"),
    ("C049","변조","fee_schedule.management_fee","운용보수(자리바꿈)","mismatch","digit_swap","medium","C011","[운용] 연[ 0.98 ] %",9,"cross_check","0.89↔0.98 자리바꿈을 놓침","정답 0.89 vs 0.98"),
    ("C050","변조","fee_schedule.management_fee","운용보수(bp 함정)","mismatch","unit_conversion","hard","C011","[운용] 연 8.9bp",9,"normalization+cross_check","8.9bp=0.089%인데 89bp(0.89%)와 혼동해 합격","bp+소수점 복합: 8.9bp=0.089%≠0.89%"),
    # fee trust
    ("C051","변조","fee_schedule.trust_fee","신탁보수(자리바꿈)","mismatch","digit_swap","medium","C012","[신탁] 연[ 0.08 ] %",9,"cross_check","초소수 보수 0.05 vs 0.08 차이를 놓침","정답 0.05 vs 0.08"),
    ("C052","변조","fee_schedule.trust_fee","신탁보수(범위 위반)","mismatch","shacl_violation","hard","C012","[신탁] 연[ 3.5 ] %",9,"g3_constraint+shacl","3.5%가 신탁보수 상한(2%) 초과인데 단위만 보고 합격","신탁보수 SHACL 0~2% 위반. 합성"),
    ("C067","정상","fee_schedule.trust_fee","신탁보수(bp 표기)","match","unit_conversion","medium","C012","[신탁] 연 5bp",9,"normalization","5bp=0.05% 환산 누락","5bp=0.05%. 합성 — IM 원본에 없음"),
    # fee sales
    ("C053","정상","fee_schedule.sales_fee","판매보수(bp 표기)","match","unit_conversion","hard","C013","[판매] 연 3bp",9,"normalization","bp 미이해로 3과 0.03을 다르다고 판단","3bp=0.03%. 합성 — IM 원본에 없음"),
    ("C054","변조","fee_schedule.sales_fee","판매보수(범위 위반)","mismatch","shacl_violation","hard","C013","[판매] 연[ 5 ] %",9,"g3_constraint+shacl","판매보수 상한(3%) 초과를 놓침","판매보수 SHACL 0~3% 위반. 합성"),
    ("C068","변조","fee_schedule.sales_fee","판매보수(자릿수 과소)","mismatch","decimal_shift","hard","C013","[판매] 연[ 0.003 ] %",9,"normalization+cross_check","0.03 vs 0.003 자릿수(과소)","10배 과소"),
    # is_redeemable
    ("C055","정상","redemption_terms.is_redeemable","환매가능(중도환매 불가)","match","semantic_equivalent","medium","C015","본 펀드는 중도환매가 불가합니다.",3,"llm_judge","'중도환매 불가'를 C015과 다른 표현이라 별개 처리","둘 다 환매불가(false). 합성 표현"),
    ("C056","변조","redemption_terms.is_redeemable","환매가능(동사 반전)","mismatch","bool_flip","medium","C015","수익자는 이 투자신탁 수익증권의 환매를 청구할 수 있다.",3,"llm_judge","동사 한글자(없다↔있다) 반전을 놓침","정답 불가 vs 변조 가능"),
    ("C057","변조","redemption_terms.is_redeemable","환매가능(분기환매 신설)","mismatch","invent_clause","hard","C015","수익자는 매 분기말 환매를 청구할 수 있습니다.",3,"llm_judge","폐쇄형인데 분기환매 조건을 IM이 신설","조건부 환매 환각 신설"),
    ("C070","정상","redemption_terms.is_redeemable","환매가능(서술 제한)","match","semantic_equivalent","hard","C015","만기 시 일시상환되는 폐쇄형으로 중도환매가 제한됩니다.",3,"llm_judge","긴 서술 속 '중도환매 제한'을 환매가능으로 오인","환매불가(false). 합성 표현"),
    # lockup
    ("C058","변조","redemption_terms.lockup_period","락업기간(환각 신설)","mismatch","invent_clause","hard","","환매금지기간(락업) 1년",9,"cross_check+llm_judge","폐쇄형은 락업 N/A인데 IM이 1년 락업 신설","락업 부재가 정상인데 IM 환각. 라벨 논의. 합성"),
    # redemption_cycle
    ("C059","변조","redemption_terms.redemption_cycle","환매주기(환각 신설)","mismatch","invent_clause","medium","","환매주기: 매 분기(분기 1회)",9,"cross_check+llm_judge","폐쇄형은 주기 N/A인데 IM이 분기주기 신설","주기 부재가 정상인데 IM 환각. 합성"),
    # redemption_fee
    ("C060","정상","redemption_terms.redemption_fee","환매수수료(없음 동치)","match","semantic_equivalent","medium","C018","환매수수료 없음",9,"llm_judge","'없음'과 '해당사항 없음'을 별개 정보로 분리","둘 다 수수료 부재. 합성 표현"),
    ("C061","변조","redemption_terms.redemption_fee","환매수수료(부과 신설)","mismatch","invent_clause","hard","C018","환매수수료 0.5%",9,"cross_check","수수료 없는 폐쇄형에 0.5% 부과를 신설","해당없음(0) vs 0.5%. 합성"),
    ("C062","변조","redemption_terms.redemption_fee","환매수수료(가짜 인용)","mismatch","fake_citation","hard","C018","환매수수료 해당사항 없음",999,"g2_citation","값은 맞지만 인용 페이지가 가짜","합성 — 가짜 인용(999). G2 전용"),
    # --- 2차 추가(표기 정규화·가드 커버리지 확장) ---
    ("C064","정상","fund.inception_date","설정일(슬래시)","match","format_diff","easy","C005","펀드설정일(예정) 2025/07/22",9,"normalization","슬래시 구분 날짜를 다른 표기로 오인","2025/07/22=2025-07-22"),
    ("C066","정상","fund.inception_date","설정일(영점 패딩)","match","format_diff","easy","C005","설정일 : 2025년 07월 22일",9,"normalization","월 0 패딩(07월)을 다른 값으로 오인","07월=7월"),
    ("C071","정상","fee_schedule.management_fee","운용보수(콤마없는 천분율)","match","unit_conversion","medium","C011","[운용] 연 1000분의 8.9",9,"normalization","콤마 없는 천분율 표기 차이","1000분의 8.9=0.89%"),
    ("C072","변조","fee_schedule.management_fee","운용보수(천분율 자리오류)","mismatch","digit_swap","hard","C011","[운용] 연 1,000분의 8.8",9,"normalization+cross_check","천분율 표기(8.8/1000)에서 8.9와의 차이를 놓침","천분율 경로 변조: 8.8/1000=0.88%≠0.89%"),
    ("C073","정상","fee_schedule.trust_fee","신탁보수(콤마없는 천분율)","match","unit_conversion","medium","C012","[신탁] 연 1000분의 0.5",9,"normalization","콤마 없는 천분율 표기 차이","1000분의 0.5=0.05%"),
    ("C074","변조","fee_schedule.sales_fee","판매보수(자리바꿈)","mismatch","digit_swap","medium","C013","[판매] 연[ 0.05 ] %",9,"cross_check","0.03 vs 0.05 차이를 놓침","정답 0.03 vs 0.05"),
    ("C075","변조","fee_schedule.management_fee","운용보수(가짜 인용)","mismatch","fake_citation","hard","C011","[운용] 연[ 0.89 ] %",999,"g2_citation","값은 맞지만 인용 페이지가 가짜","합성 — 가짜 인용(999). G2 전용"),
    ("C076","변조","fund.inception_date","설정일(가짜 인용)","mismatch","fake_citation","hard","C005","펀드설정일(예정) 2025년7월22일",999,"g2_citation","값은 맞지만 인용 페이지가 가짜","합성 — 가짜 인용(999). G2 전용"),
    ("C077","정상","fund.maturity_date","만기일(절대일자 동치)","match","semantic_equivalent","medium","C006","만기 2027년 7월 22일",9,"llm_judge","절대일자 표기를 기간(2년)과 별개로 오인","2027-07-22=설정일+2년. 합성"),
    ("C078","변조","fund.name","펀드명(호수 1→2)","mismatch","digit_swap","hard","C002","이지스블랙ON 일반사모투자신탁제2호",9,"cross_check","제1호↔제2호(자매펀드) 차이를 놓침","C026(제11호 삽입)과 다른 자리바꿈"),
    ("C079","변조","fee_schedule.trust_fee","신탁보수(자릿수 과소)","mismatch","decimal_shift","hard","C012","[신탁] 연[ 0.005 ] %",9,"normalization+cross_check","0.05 vs 0.005 자릿수(과소)","10배 과소"),
    ("C080","정상","fund.type","펀드유형(구분자)","match","list_reorder","medium","C003","투자신탁/폐쇄형/단위형/사모형/혼합자산형/일반사모집합투자기구",9,"llm_judge","슬래시 구분·순서 차이를 다른 집합으로 오인","집합 동치(구분자만 다름)"),
]


def main() -> int:
    write = "--write" in sys.argv
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        existing_rows = list(csv.DictReader(fh))
        header = list(existing_rows[0].keys())
    by_id = {r["case_id"]: r for r in existing_rows}
    anchor_raw = {cid: by_id[cid]["contract_raw"] for cid in by_id}
    anchor_page = {cid: by_id[cid]["contract_page"] for cid in by_id}
    existing_ids = set(by_id)
    seen_pairs = {(r["field"], r["label"]) for r in existing_rows}

    errors: list[str] = []
    new_rows: list[dict[str, str]] = []

    for c in NEW:
        cid, cat, field, label, gold, mut, diff, anchor, im, im_pg, signal, pit, note = c
        ctx = f"{cid}"

        # 1) 식별자/스키마 사전 검증
        if cid in existing_ids:
            errors.append(f"{ctx}: case_id 중복")
        if field not in FIELD_LABELS:
            errors.append(f"{ctx}: 미허용 field {field}")
        if (field, label) in seen_pairs:
            errors.append(f"{ctx}: (field,label) 중복 {label}")
        seen_pairs.add((field, label))
        if cat == "정상" and gold not in ("match", "missing"):
            errors.append(f"{ctx}: 정상인데 gold={gold}")
        if cat == "변조" and gold != "mismatch":
            errors.append(f"{ctx}: 변조인데 gold={gold}")

        # 2) contract_raw 출처 대조 (PM 확정본에 존재하는 문자열만)
        if anchor == "":
            c_raw, c_page = "", ""
        else:
            if anchor not in anchor_raw:
                errors.append(f"{ctx}: 앵커 {anchor} 없음")
                continue
            c_raw, c_page = anchor_raw[anchor], anchor_page[anchor]

        # 3) 수치/날짜 결정적 재계산 검증
        _verify_semantics(ctx, field, gold, mut, im, im_pg, c_raw, errors)

        new_rows.append({
            "case_id": cid, "category": cat, "field": field, "label": label,
            "gold_label": gold, "mutation_type": mut, "difficulty": diff,
            "contract_raw": c_raw, "contract_page": str(c_page) if c_page != "" else "",
            "im_raw": im, "im_page": str(im_pg) if im_pg != "" else "",
            "harness_signal": signal, "weak_model_pitfall": pit, "note": note,
        })

    # 4) 파일 기록 순서를 case_id 숫자 오름차순으로 정렬(스펙: 빈자리 허용)
    new_rows.sort(key=lambda r: int(r["case_id"][1:]))

    if errors:
        print("검증 실패:")
        for e in errors:
            print("  -", e)
        return 1

    print(f"검증 통과: 신규 {len(new_rows)}건 (총 {len(existing_rows)+len(new_rows)}건)")
    if not write:
        print("드라이런(검증만). 기록하려면 --write")
        return 0

    with CSV_PATH.open("a", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=header, lineterminator="\n")
        for r in new_rows:
            w.writerow(r)
    cases = load_golden_master(CSV_PATH)
    print(f"기록 완료. load_golden_master 재적재: {len(cases)}건 OK")
    return 0


def _verify_semantics(ctx, field, gold, mut, im, im_pg, c_raw, errors) -> None:
    """실제 하네스 비교 함수(compare_values)로 gold_label 정합성 재계산.

    - 가드 케이스(fake_citation/shacl)는 가드가 잡으므로 별도 규칙으로 검증.
    - 만기일은 derive(설정일+기간) 로직이라 캐노니컬 파서로 직접 재계산.
    - 결정적 비교가 non_decisive 면 judge 위임 케이스이므로(이름/유형/엔티티/불리언 등) 통과.
    """
    if mut == "fake_citation":
        if not (isinstance(im_pg, int) and im_pg >= 900):
            errors.append(f"{ctx}: fake_citation 인데 im_page={im_pg} (가짜 페이지여야)")
        return

    if mut == "shacl_violation":
        ic = parse_percent(im)
        lo, hi = FEE_RANGE.get(field, (None, None))
        if ic.status != "decisive":
            errors.append(f"{ctx}: shacl IM 보수 파싱 실패 '{im}'")
        elif lo is None or lo <= float(ic.value) <= hi:
            errors.append(f"{ctx}: shacl인데 {ic.value}가 범위 {lo}~{hi} 밖이 아님")
        return

    if field == "fund.maturity_date":
        idt = parse_date(im)
        if idt.status == "decisive":
            got = idt.value
        else:
            dur = parse_duration_months(im)
            if dur.status != "decisive":
                errors.append(f"{ctx}: IM 만기(날짜/기간) 파싱 실패 '{im}'")
                return
            got = add_months(INCEPTION, int(dur.value)).isoformat()
        if gold == "match" and got != MATURITY_TARGET:
            errors.append(f"{ctx}: match인데 {got}≠{MATURITY_TARGET}")
        if gold == "mismatch" and got == MATURITY_TARGET:
            errors.append(f"{ctx}: mismatch인데 {got}=={MATURITY_TARGET}")
        return

    # 그 외: 실제 하네스 compare_values 로 검증 (수치/날짜/불리언/부재)
    pol = POLICIES.get(field)
    if pol is None:
        errors.append(f"{ctx}: 필드 정책 없음 {field}")
        return
    cmp = compare_values(field, pol, (c_raw or None), im)
    fs = cmp.final_status
    if gold == "match" and fs == "different_after_normalization":
        errors.append(f"{ctx}: match인데 하네스=different (C={cmp.contract.value!r} I={cmp.im.value!r})")
    if gold == "mismatch" and fs == "same_after_normalization":
        errors.append(f"{ctx}: mismatch인데 하네스=same (C={cmp.contract.value!r} I={cmp.im.value!r})")
    # non_decisive 는 judge 위임 케이스 → 통과(오프라인 결정 불가)


if __name__ == "__main__":
    raise SystemExit(main())
