/**
 * user_activity_tracker.js - 동기식 즉시 로깅 및 렌더링 연동
 */

const UserActivityTracker = (() => {
    function getSessionContext() {
        const session = (window.AuthManager && typeof AuthManager.getCurrentSession === 'function' && AuthManager.getCurrentSession()) || null;
        const username = (session && session.user && session.user.username) ? session.user.username : 'GUEST_USER';
        const fp = (window.AuthManager && typeof AuthManager.getDeviceFingerprint === 'function')
            ? AuthManager.getDeviceFingerprint()
            : { browser: 'Chrome', os: 'PC', deviceType: 'Desktop' };
        const ipDisplay = (session && session.ip) ? session.ip : '127.0.0.1 (Local)';
        return { username, fp, ipDisplay };
    }

    function logStockSearch(stockName, stockCode, source = 'SEARCH_BAR') {
        try {
            const { username, fp, ipDisplay } = getSessionContext();
            const actionText = `SEARCH_STOCK: [${stockName}] (${stockCode || '-'}) via ${source}`;
            recordDirectAuditLog(username, fp, ipDisplay, actionText, { stockName, stockCode, type: 'SEARCH' });
        } catch (e) {
            console.error('Error logging stock search:', e);
        }
    }

    function logPaperTrading(stockName, stockCode, side, qty, price, totalAmt) {
        try {
            const { username, fp, ipDisplay } = getSessionContext();
            const actionText = `TRADE_${side}: [${stockName}] ${qty}주 @ ${Number(price).toLocaleString()}원 (총 ${Number(totalAmt).toLocaleString()}원)`;
            recordDirectAuditLog(username, fp, ipDisplay, actionText, { stockName, stockCode, side, qty, price, totalAmt, type: 'TRADE' });
        } catch (e) {
            console.error('Error logging paper trade:', e);
        }
    }

    function logWaterCalculation(stockName, currentAvg, qty, targetAvg, extraQty, budget) {
        try {
            const { username, fp, ipDisplay } = getSessionContext();
            const actionText = `CALC_WATER: [${stockName}] 매수가 ${Number(currentAvg).toLocaleString()}원 / 추가 ${extraQty}주`;
            recordDirectAuditLog(username, fp, ipDisplay, actionText, { stockName, type: 'WATER_CALC' });
        } catch (e) {
            console.error('Error logging water calc:', e);
        }
    }

    function recordDirectAuditLog(username, fp, ipDisplay, action, meta) {
        const STORAGE_KEY = 'cpr_auth_logs_v2';
        let logs = [];
        try {
            const raw = localStorage.getItem(STORAGE_KEY) || localStorage.getItem('cpr_auth_logs');
            logs = raw ? JSON.parse(raw) : [];
        } catch (_) { logs = []; }

        logs.unshift({
            id: Date.now() + Math.random(),
            username: username,
            ip: ipDisplay,
            browser: (fp && fp.browser) || 'Browser',
            os: (fp && fp.os) || 'OS',
            deviceType: (fp && fp.deviceType) || 'Desktop',
            action: action,
            meta: meta || {},
            time: new Date().toLocaleTimeString('ko-KR')
        });

        const sliced = JSON.stringify(logs.slice(0, 500));
        localStorage.setItem(STORAGE_KEY, sliced);
        localStorage.setItem('cpr_auth_logs', sliced);

        // 만약 통제실 모달이 열려있다면 즉시 실시간 리렌더링
        const adminModal = document.getElementById('admin-modal');
        if (adminModal && adminModal.style.display !== 'none' && typeof renderAdminAuditLogs === 'function') {
            renderAdminAuditLogs();
        }
    }

    return {
        logStockSearch,
        logPaperTrading,
        logWaterCalculation,
        recordDirectAuditLog
    };
})();

window.UserActivityTracker = UserActivityTracker;
