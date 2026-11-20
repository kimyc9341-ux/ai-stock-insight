/**
 * auth_manager.js - 최고관리자 심사용 계정(admin2 등) 확인, 권한 부여/제한, 추가 발급 완성형
 */

const AuthManager = (() => {
    const STORAGE_KEY_SESSION = 'cpr_auth_session';
    const STORAGE_KEY_USERS = 'cpr_users_v2';
    const STORAGE_KEY_LOGS = 'cpr_auth_logs_v2';
    const STORAGE_KEY_REVIEW_CODES = 'cpr_review_codes';
    let cachedClientIpInfo = null;

    async function resolvePublicIp() {
        if (cachedClientIpInfo) return cachedClientIpInfo;
        try {
            const res = await fetch('https://ipapi.co/json/');
            if (res.ok) {
                const data = await res.json();
                cachedClientIpInfo = {
                    ip: data.ip || '127.0.0.1',
                    city: data.city || data.region || '대한민국',
                    display: `${data.ip} (${data.city || data.region || '대한민국'})`
                };
                return cachedClientIpInfo;
            }
        } catch (_) {}

        try {
            const res = await fetch('https://api.ipify.org?format=json');
            if (res.ok) {
                const data = await res.json();
                cachedClientIpInfo = { ip: data.ip, display: `${data.ip} (공인 IP)` };
                return cachedClientIpInfo;
            }
        } catch (_) {}

        cachedClientIpInfo = { ip: '127.0.0.1 (Local)', display: '127.0.0.1 (Local)' };
        return cachedClientIpInfo;
    }

    function getDeviceFingerprint() {
        const ua = navigator.userAgent;
        let browser = 'Chrome';
        if (ua.includes('Firefox')) browser = 'Firefox';
        else if (ua.includes('SamsungBrowser')) browser = 'Samsung Internet';
        else if (ua.includes('Safari') && !ua.includes('Chrome')) browser = 'Safari';
        else if (ua.includes('Edge')) browser = 'Edge';

        let os = 'Windows';
        if (ua.includes('Mac')) os = 'macOS';
        else if (ua.includes('Linux')) os = 'Linux';
        else if (ua.includes('Android')) os = 'Android';
        else if (ua.includes('iPhone') || ua.includes('iPad')) os = 'iOS';

        const deviceType = /Mobi|Android/i.test(ua) ? 'Mobile' : 'Desktop';

        return {
            browser,
            os,
            deviceType,
            userAgent: ua,
            timestamp: new Date().toISOString()
        };
    }

    function initDatabase() {
        // 기존 버전 스토리지 자동 마이그레이션 (admin 세션 및 role 보장)
        const storedUsers = localStorage.getItem(STORAGE_KEY_USERS);
        if (!storedUsers) {
            const defaultUsers = [
                {
                    id: 'usr-admin',
                    username: 'admin',
                    password: '1234',
                    name: '최고 관리자',
                    birthdate: '1990-01-01',
                    phone: '010-0000-0000',
                    isPhoneVerified: true,
                    email: 'admin@myaccount.local',
                    address: '서울특별시 영등포구 여의도동',
                    referrer: 'SYSTEM',
                    role: 'admin',
                    status: 'approved',
                    allowExternalQuery: true,
                    apiKeyEnabled: true,
                    canAccessAdminPanel: true,
                    created_at: new Date().toISOString()
                }
            ];
            localStorage.setItem(STORAGE_KEY_USERS, JSON.stringify(defaultUsers));
        } else {
            const users = JSON.parse(storedUsers);
            let admin = users.find(u => u.username === 'admin');
            if (admin) {
                admin.role = 'admin';
                admin.canAccessAdminPanel = true;
                localStorage.setItem(STORAGE_KEY_USERS, JSON.stringify(users));
            }
        }

        // 심사용 계정 기본 목록 (admin2 / 5678)
        const defaultReviewAccounts = [
            {
                username: 'admin2',
                password: '5678',
                name: '심사 담당자',
                note: '심사용 공식 계정',
                isActive: true,
                canAccessAdminPanel: true, // 최고관리자가 보안통제실에서 ON/OFF 토글 가능
                created_at: new Date().toISOString()
            }
        ];

        const storedCodes = localStorage.getItem(STORAGE_KEY_REVIEW_CODES);
        if (!storedCodes) {
            localStorage.setItem(STORAGE_KEY_REVIEW_CODES, JSON.stringify(defaultReviewAccounts));
        } else {
            const codes = JSON.parse(storedCodes);
            let target = codes.find(c => c.username === 'admin2');
            if (!target) {
                codes.unshift(defaultReviewAccounts[0]);
                localStorage.setItem(STORAGE_KEY_REVIEW_CODES, JSON.stringify(codes));
            }
        }

        if (!localStorage.getItem(STORAGE_KEY_LOGS)) {
            localStorage.setItem(STORAGE_KEY_LOGS, JSON.stringify([]));
        }
        resolvePublicIp();
    }

    function getUsers() {
        initDatabase();
        return JSON.parse(localStorage.getItem(STORAGE_KEY_USERS) || '[]');
    }

    function saveUsers(users) {
        localStorage.setItem(STORAGE_KEY_USERS, JSON.stringify(users));
    }

    function getReviewCodes() {
        initDatabase();
        return JSON.parse(localStorage.getItem(STORAGE_KEY_REVIEW_CODES) || '[]');
    }

    function saveReviewCodes(codes) {
        localStorage.setItem(STORAGE_KEY_REVIEW_CODES, JSON.stringify(codes));
    }

    function getCurrentSession() {
        const s = localStorage.getItem(STORAGE_KEY_SESSION);
        return s ? JSON.parse(s) : null;
    }

    function isLoggedIn() {
        const session = getCurrentSession();
        return !!(session && session.user && session.user.status === 'approved');
    }

    // 심사용 아이디 로그인 (아이디 + 비밀번호)
    async function loginWithReviewCode(username, password) {
        initDatabase();
        const cleanUser = username.trim().toLowerCase();
        const codes = getReviewCodes();
        const target = codes.find(c => c.username.toLowerCase() === cleanUser);
        const fp = getDeviceFingerprint();
        const ipInfo = await resolvePublicIp();

        if (!target) {
            recordLog(username, fp, ipInfo, 'EVAL_LOGIN_FAIL_USER');
            return { success: false, message: '등록되지 않은 심사용 아이디입니다.' };
        }

        if (target.password !== password) {
            recordLog(username, fp, ipInfo, 'EVAL_LOGIN_FAIL_PW');
            return { success: false, message: '비밀번호가 일치하지 않습니다.' };
        }

        if (!target.isActive) {
            recordLog(username, fp, ipInfo, 'EVAL_LOGIN_BLOCKED');
            return { success: false, message: '이용이 중지된 심사용 계정입니다. 관리자에게 문의하세요.' };
        }

        const session = {
            user: {
                id: 'eval-' + target.username,
                username: target.username,
                name: target.name || '심사평가자',
                role: 'evaluator',
                status: 'approved',
                isReviewer: true,
                allowExternalQuery: true,
                apiKeyEnabled: true,
                canAccessAdminPanel: target.canAccessAdminPanel !== false
            },
            device: fp,
            ip: ipInfo.display,
            loggedInAt: new Date().toISOString()
        };

        localStorage.setItem(STORAGE_KEY_SESSION, JSON.stringify(session));
        recordLog(target.username, fp, ipInfo, 'EVAL_LOGIN_SUCCESS');

        return { success: true, session, message: '심사용 계정 로그인이 완료되었습니다.' };
    }

    // 최고관리자 전용: 심사용 아이디 추가 발급
    function createReviewAccount(username, password, name, note = '', canAccessAdmin = true) {
        const session = getCurrentSession();
        if (!session || session.user.role !== 'admin') {
            return { success: false, message: '최고관리자만 심사용 아이디를 발급할 수 있습니다.' };
        }

        const codes = getReviewCodes();
        const cleanUser = username.trim().toLowerCase();

        if (!cleanUser || cleanUser.length < 3) return { success: false, message: '아이디는 3자리 이상이어야 합니다.' };
        if (!password || password.length < 4) return { success: false, message: '비밀번호는 4자리 이상이어야 합니다.' };

        if (codes.some(c => c.username.toLowerCase() === cleanUser)) {
            return { success: false, message: '이미 존재하는 심사용 아이디입니다.' };
        }

        codes.unshift({
            username: cleanUser,
            password: password,
            name: name.trim() || cleanUser,
            note: note.trim() || '추가 발급된 심사용 계정',
            isActive: true,
            canAccessAdminPanel: canAccessAdmin,
            created_at: new Date().toISOString()
        });
        saveReviewCodes(codes);
        return { success: true, message: `새로운 심사용 아이디 [ ${cleanUser} ] 가 성공적으로 발급되었습니다.` };
    }

    // 최고관리자 전용: 심사용 아이디의 보안통제실 권한 ON/OFF 토글
    function toggleAdminPanelAccess(username, canAccess) {
        const session = getCurrentSession();
        if (!session || session.user.role !== 'admin') {
            alert('최고관리자만 통제실 권한을 변경할 수 있습니다.');
            return false;
        }

        const codes = getReviewCodes();
        const target = codes.find(c => c.username.toLowerCase() === username.toLowerCase());
        if (target) {
            target.canAccessAdminPanel = canAccess;
            saveReviewCodes(codes);
            return true;
        }
        return false;
    }

    function toggleReviewCodeStatus(username, isActive) {
        const session = getCurrentSession();
        if (!session || session.user.role !== 'admin') {
            alert('최고관리자만 계정 상태를 변경할 수 있습니다.');
            return false;
        }

        const codes = getReviewCodes();
        const target = codes.find(c => c.username === username);
        if (target) {
            target.isActive = isActive;
            saveReviewCodes(codes);
            return true;
        }
        return false;
    }

    // 일반 로그인
    async function login(username, password) {
        initDatabase();
        const users = getUsers();
        const user = users.find(u => u.username.toLowerCase() === username.toLowerCase().trim());
        const fp = getDeviceFingerprint();
        const ipInfo = await resolvePublicIp();

        if (!user) {
            return { success: false, message: '등록되지 않은 아이디입니다. 회원가입을 먼저 진행해 주세요.' };
        }

        if (user.password !== password) {
            recordLog(user.username, fp, ipInfo, 'LOGIN_FAIL_PASSWORD');
            return { success: false, message: '비밀번호가 일치하지 않습니다. 다시 확인해 주세요.' };
        }

        if (user.status === 'pending') {
            recordLog(user.username, fp, ipInfo, 'LOGIN_BLOCKED_PENDING');
            return { success: false, message: '가입 승인 심사 대기 중인 계정입니다. 관리자 승인 확인 후 로그인 가능합니다.' };
        }

        if (user.status === 'blocked') {
            recordLog(user.username, fp, ipInfo, 'LOGIN_BLOCKED');
            return { success: false, message: '관리자에 의해 이용이 차단된 계정입니다.' };
        }

        const session = {
            user: {
                id: user.id,
                username: user.username,
                name: user.name,
                birthdate: user.birthdate,
                phone: user.phone,
                email: user.email,
                address: user.address,
                referrer: user.referrer,
                role: user.role,
                status: user.status,
                allowExternalQuery: user.allowExternalQuery,
                apiKeyEnabled: user.apiKeyEnabled,
                canAccessAdminPanel: user.role === 'admin'
            },
            device: fp,
            ip: ipInfo.display,
            loggedInAt: new Date().toISOString()
        };

        localStorage.setItem(STORAGE_KEY_SESSION, JSON.stringify(session));
        recordLog(user.username, fp, ipInfo, 'LOGIN_SUCCESS');

        return { success: true, session };
    }

    // 정밀 회원가입
    async function register(formData) {
        initDatabase();
        const { username, password, name, birthdate, phone, isPhoneVerified, email, address, referrer } = formData;
        const ipInfo = await resolvePublicIp();

        if (!isPhoneVerified) return { success: false, message: '휴대폰 본인 실명인증을 먼저 완료해 주세요.' };
        if (!name || name.trim().length < 2) return { success: false, message: '이름(실명)을 정확히 입력해 주세요.' };
        if (!birthdate) return { success: false, message: '생년월일을 입력해 주세요.' };

        const cleanUser = username.trim().toLowerCase();
        if (!cleanUser || cleanUser.length < 3) return { success: false, message: '아이디는 3자리 이상이어야 합니다.' };
        if (!password || password.length < 4) return { success: false, message: '비밀번호는 최소 4자리 이상이어야 합니다.' };

        const users = getUsers();
        if (users.some(u => u.username.toLowerCase() === cleanUser)) {
            return { success: false, message: '이미 사용 중인 아이디입니다.' };
        }

        if (referrer && referrer.trim() && !users.some(u => u.username.toLowerCase() === referrer.trim().toLowerCase())) {
            return { success: false, message: `추천인 아이디('${referrer}')를 찾을 수 없습니다.` };
        }

        const newUser = {
            id: 'usr-' + Date.now().toString(36),
            username: cleanUser,
            password: password,
            name: name.trim(),
            birthdate: birthdate,
            phone: phone,
            isPhoneVerified: true,
            email: email.trim(),
            address: address.trim(),
            referrer: referrer.trim() || '없음',
            regIp: ipInfo.display,
            role: cleanUser === 'admin' ? 'admin' : 'user',
            status: cleanUser === 'admin' ? 'approved' : 'pending',
            allowExternalQuery: cleanUser === 'admin',
            apiKeyEnabled: cleanUser === 'admin',
            canAccessAdminPanel: cleanUser === 'admin',
            created_at: new Date().toISOString()
        };

        users.push(newUser);
        saveUsers(users);

        recordLog(cleanUser, getDeviceFingerprint(), ipInfo, 'REGISTER_SUBMITTED');

        return {
            success: true,
            message: '회원가입 신청이 성공적으로 접수되었습니다!\n관리자 승인 후 정식 서비스 이용이 가능합니다.'
        };
    }

    // 회원정보 수정
    async function updateProfile(username, currentPw, newPw, updatedData) {
        initDatabase();
        const users = getUsers();
        const user = users.find(u => u.username.toLowerCase() === username.toLowerCase().trim());
        const session = getCurrentSession();

        if (!user) return { success: false, message: '사용자를 찾을 수 없습니다.' };
        if (user.password !== currentPw) return { success: false, message: '현재 비밀번호가 올바르지 않습니다.' };

        if (newPw) {
            if (newPw.length < 4) return { success: false, message: '새 비밀번호는 4자리 이상이어야 합니다.' };
            user.password = newPw;
        }

        if (updatedData.name) user.name = updatedData.name.trim();
        if (updatedData.phone) user.phone = updatedData.phone.trim();
        if (updatedData.email) user.email = updatedData.email.trim();
        if (updatedData.address) user.address = updatedData.address.trim();

        saveUsers(users);

        if (session && session.user && session.user.username.toLowerCase() === username.toLowerCase()) {
            session.user.name = user.name;
            session.user.phone = user.phone;
            session.user.email = user.email;
            session.user.address = user.address;
            localStorage.setItem(STORAGE_KEY_SESSION, JSON.stringify(session));
        }

        const ipInfo = await resolvePublicIp();
        recordLog(username, getDeviceFingerprint(), ipInfo, newPw ? 'PASSWORD_CHANGED' : 'PROFILE_UPDATED');

        return { success: true, message: '회원정보가 안전하게 업데이트되었습니다.' };
    }

    // 로그아웃
    async function logout() {
        const session = getCurrentSession();
        if (session) {
            const ipInfo = await resolvePublicIp();
            recordLog(session.user.username, getDeviceFingerprint(), ipInfo, 'LOGOUT');
        }
        localStorage.removeItem(STORAGE_KEY_SESSION);
        sessionStorage.clear();
        return true;
    }

    function recordLog(username, fp, ipInfo, action) {
        const logs = JSON.parse(localStorage.getItem(STORAGE_KEY_LOGS) || '[]');
        logs.unshift({
            id: Date.now(),
            username: username,
            ip: (ipInfo && ipInfo.display) ? ipInfo.display : '127.0.0.1 (Local)',
            browser: fp.browser,
            os: fp.os,
            deviceType: fp.deviceType,
            action: action,
            time: new Date().toLocaleTimeString('ko-KR')
        });
        localStorage.setItem(STORAGE_KEY_LOGS, JSON.stringify(logs.slice(0, 300)));
    }

    function getAuditLogs() {
        initDatabase();
        return JSON.parse(localStorage.getItem(STORAGE_KEY_LOGS) || '[]');
    }

    function updateMemberStatus(userId, newStatus) {
        const users = getUsers();
        const target = users.find(u => u.id === userId);
        if (target) {
            target.status = newStatus;
            saveUsers(users);
            return true;
        }
        return false;
    }

    function toggleExternalQuery(userId, isAllowed) {
        const users = getUsers();
        const target = users.find(u => u.id === userId);
        if (target) {
            target.allowExternalQuery = isAllowed;
            saveUsers(users);
            return true;
        }
        return false;
    }

    function toggleApiKey(userId, isEnabled) {
        const users = getUsers();
        const target = users.find(u => u.id === userId);
        if (target) {
            target.apiKeyEnabled = isEnabled;
            saveUsers(users);
            return true;
        }
        return false;
    }

    return {
        initDatabase,
        getUsers,
        getCurrentSession,
        isLoggedIn,
        login,
        loginWithReviewCode,
        createReviewAccount,
        getReviewCodes,
        toggleReviewCodeStatus,
        toggleAdminPanelAccess,
        register,
        updateProfile,
        logout,
        getAuditLogs,
        updateMemberStatus,
        toggleExternalQuery,
        toggleApiKey,
        resolvePublicIp
    };
})();

window.AuthManager = AuthManager;
AuthManager.initDatabase();
