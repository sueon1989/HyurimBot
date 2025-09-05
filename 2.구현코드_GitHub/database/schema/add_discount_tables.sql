-- 할인정책 관련 테이블 추가 (기존 데이터 보존)
-- 생성일: 2025-09-04

-- 할인정책 메인 테이블
CREATE TABLE IF NOT EXISTS discount_policies (
    discount_id INTEGER PRIMARY KEY AUTOINCREMENT,
    forest_id TEXT NOT NULL,
    policy_category TEXT NOT NULL,    -- '숙박동할인', '입장료면제'
    target_group TEXT NOT NULL,       -- '다자녀가정', '장애인', '지역주민' 등
    discount_type TEXT NOT NULL,      -- 'percentage', 'exemption'
    discount_rate INTEGER,            -- 할인율 (30, 50 등)
    conditions TEXT,                  -- 적용 조건 ('비수기 주중에 한함' 등)
    required_documents TEXT,          -- 필요 서류
    detailed_description TEXT,        -- 상세 설명
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (forest_id) REFERENCES forests(forest_id)
);

-- 할인정책 상세 조건 테이블
CREATE TABLE IF NOT EXISTS discount_conditions (
    condition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    discount_id INTEGER,
    condition_type TEXT,              -- 'grade', 'age', 'residence' 등
    condition_value TEXT,             -- '1-3급', '12세이하', '제주도민' 등
    FOREIGN KEY (discount_id) REFERENCES discount_policies(discount_id)
);

-- 인덱스 생성 (성능 최적화)
CREATE INDEX IF NOT EXISTS idx_discount_policies_forest_id ON discount_policies(forest_id);
CREATE INDEX IF NOT EXISTS idx_discount_policies_target_group ON discount_policies(target_group);
CREATE INDEX IF NOT EXISTS idx_discount_conditions_discount_id ON discount_conditions(discount_id);