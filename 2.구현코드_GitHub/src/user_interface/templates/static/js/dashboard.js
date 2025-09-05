// HyurimBot 관리자 대시보드 JavaScript

class DashboardManager {
    constructor() {
        this.forests = [];
        this.accommodations = [];
        this.discounts = [];
        this.init();
    }

    init() {
        // 초기 데이터 로드 - 자연휴양림 탭이 기본이므로 먼저 로드
        this.loadForests();
        this.loadAccommodations();
        this.loadDiscounts();
        
        // 이벤트 리스너 설정
        this.setupEventListeners();
    }

    setupEventListeners() {
        // 숙박시설 필터
        const accommodationFilter = document.getElementById('accommodationForestFilter');
        if (accommodationFilter) {
            accommodationFilter.addEventListener('change', (e) => {
                this.loadAccommodations(e.target.value);
            });
        }

        // 할인정책 필터
        const discountFilter = document.getElementById('discountForestFilter');
        if (discountFilter) {
            discountFilter.addEventListener('change', (e) => {
                this.loadDiscounts(e.target.value);
            });
        }
    }

    // 자연휴양림 데이터 로드
    async loadForests() {
        try {
            const response = await fetch('/api/forests');
            const forests = await response.json();
            this.forests = forests;
            this.populateForestFilters(forests);
            this.renderForestsTable(forests);
        } catch (error) {
            console.error('Failed to load forests:', error);
            this.showError('자연휴양림 데이터를 불러오는데 실패했습니다.');
        }
    }

    // 숙박시설 데이터 로드
    async loadAccommodations(forestId = null) {
        try {
            const url = forestId ? `/api/accommodations?forest_id=${forestId}` : '/api/accommodations';
            const response = await fetch(url);
            const accommodations = await response.json();
            this.accommodations = accommodations;
            this.renderAccommodationsTable(accommodations);
        } catch (error) {
            console.error('Failed to load accommodations:', error);
            this.showError('숙박시설 데이터를 불러오는데 실패했습니다.');
        }
    }


    // 할인정책 데이터 로드
    async loadDiscounts(forestId = null) {
        try {
            const url = forestId ? `/api/discounts?forest_id=${forestId}` : '/api/discounts';
            const response = await fetch(url);
            const discounts = await response.json();
            this.discounts = discounts;
            this.renderDiscountsTable(discounts);
        } catch (error) {
            console.error('Failed to load discounts:', error);
            this.showError('할인정책 데이터를 불러오는데 실패했습니다.');
        }
    }

    // 새로운 데이터 수집 메서드들
    async collectForestData(forestId) {
        if (!forestId) return;
        
        this.showCrawlingStatus('기본 데이터 수집을 시작합니다...', 'info');
        this.showLoadingModal();

        try {
            const response = await fetch('/api/crawl/basic', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ forest_id: forestId })
            });

            const result = await response.json();
            this.hideLoadingModal();

            if (result.status === 'success') {
                this.showCrawlingStatus(result.message, 'success');
                await this.loadForests();
                await this.loadAccommodations();
            } else {
                this.showCrawlingStatus(result.message, result.status);
            }
        } catch (error) {
            this.hideLoadingModal();
            console.error('Forest data collection error:', error);
            this.showCrawlingStatus('데이터 수집 중 오류가 발생했습니다.', 'error');
        }
    }
    
    async collectAccommodationData(forestId, accommodationId) {
        if (!forestId || !accommodationId) return;
        
        this.showCrawlingStatus('상세 데이터 수집을 시작합니다...', 'info');
        this.showLoadingModal();

        try {
            const response = await fetch('/api/crawl/detailed', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    forest_id: forestId,
                    accommodation_id: accommodationId 
                })
            });

            const result = await response.json();
            this.hideLoadingModal();

            if (result.status === 'success') {
                this.showCrawlingStatus(result.message, 'success');
                await this.loadAccommodations();
                await this.loadForests(); // 휴양림 데이터 상태 업데이트
            } else {
                this.showCrawlingStatus(result.message, result.status);
            }
        } catch (error) {
            this.hideLoadingModal();
            console.error('Accommodation data collection error:', error);
            this.showCrawlingStatus('상세 데이터 수집 중 오류가 발생했습니다.', 'error');
        }
    }



    // UI 업데이트 메서드들

    populateForestFilters(forests) {
        const accommodationFilter = document.getElementById('accommodationForestFilter');
        const discountFilter = document.getElementById('discountForestFilter');
        
        [accommodationFilter, discountFilter].forEach(filter => {
            if (filter) {
                filter.innerHTML = '<option value="">전체 휴양림</option>';
                forests.forEach(forest => {
                    const option = document.createElement('option');
                    option.value = forest.forest_id;
                    option.textContent = forest.forest_name;
                    filter.appendChild(option);
                });
            }
        });
    }

    renderForestsTable(forests) {
        const tbody = document.getElementById('forestsTableBody');
        
        if (forests.length === 0) {
            tbody.innerHTML = '<tr><td colspan="11" class="text-center">데이터가 없습니다.</td></tr>';
            return;
        }

        tbody.innerHTML = forests.map(forest => {
            return `
            <tr>
                <td><strong>${forest.forest_name}</strong></td>
                <td>${forest.sido}</td>
                <td><span class="badge bg-info">${forest.forest_type || '-'}</span></td>
                <td><span class="badge ${forest.accommodation_available === 'Y' ? 'bg-success' : 'bg-secondary'}">${forest.accommodation_available === 'Y' ? '가능' : '불가능'}</span></td>
                <td class="facilities"><small>${this.truncateText(forest.main_facilities, 35)}</small></td>
                <td class="address"><small>${this.truncateText(forest.address, 50)}</small></td>
                <td><small>${forest.phone || '-'}</small></td>
                <td class="homepage">
                    ${forest.homepage_url ? `<a href="${forest.homepage_url}" target="_blank" class="btn btn-sm btn-outline-info"><i class="fas fa-external-link-alt"></i></a>` : '-'}
                </td>
                <td>
                    ${this.renderBasicDataCollectionButton(forest.forest_id, forest.has_basic_data)}
                </td>
                <td>
                    ${this.renderDiscountDataCollectionButton(forest.forest_id, forest.has_discount_data)}
                </td>
                <td class="update-time">
                    ${forest.updated_at && forest.updated_at !== '-' ? this.formatDateTime(forest.updated_at) : '-'}
                </td>
            </tr>
            `;
        }).join('');
    }

    renderAccommodationsTable(accommodations) {
        const tbody = document.getElementById('accommodationsTableBody');
        
        if (accommodations.length === 0) {
            tbody.innerHTML = '<tr><td colspan="15" class="text-center">데이터가 없습니다.</td></tr>';
            return;
        }

        tbody.innerHTML = accommodations.map(acc => {
            // 면적 데이터 처리 - area 또는 area_sqm에서 숫자만 추출
            const areaText = acc.area || '0';
            const areaSqm = parseFloat(areaText.toString().replace(/[^0-9.]/g, '')) || 0;
            const areaPyeong = areaSqm > 0 ? (areaSqm / 3.3058).toFixed(1) : '0';
            
            // 비수기주말 및 성수기 가격 - 비수기주말을 우선 표시하고 없으면 성수기 가격 사용
            const combinedWeekendPrice = acc.price_off_weekend > 0 ? acc.price_off_weekend : 
                                       (acc.price_peak_weekend > 0 ? acc.price_peak_weekend : 0);
            
            return `
            <tr>
                <td class="forest-name">${acc.forest_name}</td>
                <td><span class="badge bg-secondary">${acc.facility_type || '-'}</span></td>
                <td class="facility-name">${acc.facility_name}</td>
                <td class="capacity-standard">${acc.capacity_standard || '-'}인</td>
                <td class="capacity-maximum">${acc.capacity_maximum || acc.capacity_standard || '-'}인</td>
                <td class="area-sqm">${areaSqm > 0 ? areaSqm : '-'}</td>
                <td class="area-pyeong">${areaPyeong > 0 ? areaPyeong : '-'}평</td>
                <td class="checkin-time">${acc.checkin_time || '-'}</td>
                <td class="checkout-time">${acc.checkout_time || '-'}</td>
                <td class="price-off-weekday ${acc.price_off_weekday > 0 ? 'price-cell' : 'price-zero'}">
                    ${acc.price_off_weekday > 0 ? acc.price_off_weekday.toLocaleString() + '원' : '-'}
                </td>
                <td class="price-combined-weekend ${combinedWeekendPrice > 0 ? 'price-cell' : 'price-zero'}">
                    ${combinedWeekendPrice > 0 ? combinedWeekendPrice.toLocaleString() + '원' : '-'}
                </td>
                <td class="amenities-cell">
                    <small title="${acc.amenities || ''}">${this.truncateText(this.formatList(acc.amenities), 30)}</small>
                </td>
                <td class="usage-info">
                    <small title="${acc.usage_info || ''}">${this.truncateText(acc.usage_info, 50)}</small>
                </td>
                <td>
                    ${this.renderDetailedDataCollectionButton(acc.forest_id, acc.accommodation_id, acc.has_detailed_data)}
                </td>
                <td class="update-time">
                    ${acc.updated_at && acc.updated_at !== '-' ? this.formatDateTime(acc.updated_at) : '-'}
                </td>
            </tr>
            `;
        }).join('');
    }


    renderDiscountsTable(discounts) {
        const tbody = document.getElementById('discountsTableBody');
        
        if (discounts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" class="text-center">데이터가 없습니다.</td></tr>';
            return;
        }

        tbody.innerHTML = discounts.map(discount => `
            <tr>
                <td>${discount.forest_name}</td>
                <td><span class="badge bg-secondary">${discount.policy_category || '-'}</span></td>
                <td>${discount.target_group || '-'}</td>
                <td><span class="badge bg-info">${discount.discount_type === 'percentage' ? '할인' : '면제' || '-'}</span></td>
                <td>${discount.discount_rate ? discount.discount_rate + '%' : '-'}</td>
                <td><small>${this.truncateText(discount.conditions, 30)}</small></td>
                <td><small>${this.truncateText(discount.required_documents, 25)}</small></td>
                <td><small>${this.truncateText(discount.detailed_description, 40)}</small></td>
                <td>
                    ${this.renderDiscountDataCollectionButton(discount.forest_id, discount.has_detailed_data)}
                </td>
                <td class="update-time">
                    ${discount.updated_at && discount.updated_at !== '-' ? this.formatDateTime(discount.updated_at) : '-'}
                </td>
            </tr>
        `).join('');
    }

    // 유틸리티 메서드들

    renderDataStatusBadge(status) {
        switch (status) {
            case 'detailed':
                return '<span class="badge bg-success">상세</span>';
            case 'basic':
                return '<span class="badge bg-info">기본</span>';
            default:
                return '<span class="badge bg-secondary">미수집</span>';
        }
    }

    renderBasicDataCollectionButton(forestId, hasBasicData) {
        if (hasBasicData) {
            return `<button class="btn btn-sm btn-outline-warning" onclick="dashboard.collectForestData('${forestId}')">
                <i class="fas fa-sync-alt me-1"></i>데이터 갱신
            </button>`;
        } else {
            return `<button class="btn btn-sm btn-warning" onclick="dashboard.collectForestData('${forestId}')">
                <i class="fas fa-download me-1"></i>데이터 수집
            </button>`;
        }
    }

    renderDetailedDataCollectionButton(forestId, accommodationId, hasDetailedData) {
        if (hasDetailedData) {
            return `<button class="btn btn-sm btn-outline-primary" onclick="dashboard.collectAccommodationData('${forestId}', ${accommodationId})">
                <i class="fas fa-sync-alt me-1"></i>데이터 갱신
            </button>`;
        } else {
            return `<button class="btn btn-sm btn-primary" onclick="dashboard.collectAccommodationData('${forestId}', ${accommodationId})">
                <i class="fas fa-search-plus me-1"></i>데이터 수집
            </button>`;
        }
    }

    renderDiscountStatusBadge(status) {
        switch (status) {
            case 'collected':
                return '<span class="badge bg-success">수집완료</span>';
            case 'partial':
                return '<span class="badge bg-warning">일부수집</span>';
            default:
                return '<span class="badge bg-secondary">미수집</span>';
        }
    }

    renderDiscountDataCollectionButton(forestId, hasDiscountData) {
        if (hasDiscountData) {
            return `<button class="btn btn-sm btn-outline-success" onclick="dashboard.collectDiscountData('${forestId}')">
                <i class="fas fa-sync-alt me-1"></i>데이터 갱신
            </button>`;
        } else {
            return `<button class="btn btn-sm btn-success" onclick="dashboard.collectDiscountData('${forestId}')">
                <i class="fas fa-percent me-1"></i>할인정책 수집
            </button>`;
        }
    }

    async collectDiscountData(forestId) {
        if (!forestId) return;
        
        this.showCrawlingStatus('할인정책 데이터 수집을 시작합니다...', 'info');
        this.showLoadingModal();

        try {
            const response = await fetch('/api/crawl/discount-policies', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ forest_id: forestId })
            });

            const result = await response.json();
            this.hideLoadingModal();

            if (result.status === 'success') {
                this.showCrawlingStatus(result.message, 'success');
                await this.loadDiscounts();
                await this.loadForests(); // 휴양림 데이터 상태 업데이트
            } else {
                this.showCrawlingStatus(result.message, result.status);
            }
        } catch (error) {
            this.hideLoadingModal();
            console.error('Discount data collection error:', error);
            this.showCrawlingStatus('할인정책 데이터 수집 중 오류가 발생했습니다.', 'error');
        }
    }

    getDataStatusBadgeClass(status) {
        switch (status) {
            case 'detailed': return 'badge-detailed';
            case 'basic': return 'badge-basic';
            default: return 'badge-empty';
        }
    }

    getDataStatusText(status) {
        switch (status) {
            case 'detailed': return '상세';
            case 'basic': return '기본';
            default: return '미수집';
        }
    }
    

    truncateText(text, maxLength) {
        if (!text) return '-';
        return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    }

    formatList(text) {
        if (!text) return '-';
        // 세미콜론으로 구분된 리스트를 콤마로 변경
        return text.replace(/;/g, ', ');
    }

    formatDateTime(dateString) {
        if (!dateString || dateString === '-') return '-';
        try {
            // ISO 형식 날짜를 한국 형식으로 변환
            const date = new Date(dateString);
            if (isNaN(date.getTime())) return '-';
            return date.toLocaleDateString('ko-KR') + ' ' + date.toLocaleTimeString('ko-KR', {hour: '2-digit', minute: '2-digit'});
        } catch (error) {
            console.warn('Date parsing error:', error);
            return '-';
        }
    }

    showCrawlingStatus(message, type) {
        const statusElement = document.getElementById('crawlStatus');
        const messageElement = document.getElementById('statusMessage');
        
        statusElement.style.display = 'block';
        messageElement.textContent = message;
        
        // 알림 클래스 제거 후 새로 추가
        statusElement.className = 'mt-3';
        statusElement.classList.add('alert');
        
        switch (type) {
            case 'success':
                statusElement.classList.add('alert-success');
                break;
            case 'error':
                statusElement.classList.add('alert-danger');
                break;
            case 'warning':
                statusElement.classList.add('alert-warning');
                break;
            default:
                statusElement.classList.add('alert-info');
        }

        // 5초 후 자동으로 숨기기 (success 메시지의 경우)
        if (type === 'success') {
            setTimeout(() => {
                statusElement.style.display = 'none';
            }, 5000);
        }
    }

    showError(message) {
        alert(message);
    }

    showLoadingModal() {
        const modal = new bootstrap.Modal(document.getElementById('loadingModal'));
        modal.show();
    }

    hideLoadingModal() {
        const modal = bootstrap.Modal.getInstance(document.getElementById('loadingModal'));
        if (modal) {
            modal.hide();
        }
    }
}

// 글로벌 함수들 (HTML에서 호출)
function loadForests() {
    dashboard.loadForests();
}

function loadAccommodations() {
    dashboard.loadAccommodations();
}


function loadDiscounts() {
    dashboard.loadDiscounts();
}

// 페이지 로드 시 초기화
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new DashboardManager();
});