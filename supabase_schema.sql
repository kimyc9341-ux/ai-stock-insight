-- ==============================================================================
-- 🩺 [내 계좌 심폐소생술] Supabase Auth, RLS 및 관리자 통제 스키마
-- ==============================================================================

-- 1. 프로필 및 권한 테이블 (profiles)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('admin', 'user')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'blocked')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 접속 기기 및 감사 로그 테이블 (access_logs)
CREATE TABLE IF NOT EXISTS public.access_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    email TEXT,
    ip_address TEXT,
    browser TEXT,
    os TEXT,
    device_type TEXT,
    user_agent TEXT,
    action TEXT DEFAULT 'LOGIN',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. API 키 및 외부조회 제어 테이블 (api_controls)
CREATE TABLE IF NOT EXISTS public.api_controls (
    user_id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
    allow_external_query BOOLEAN DEFAULT TRUE,
    api_key_enabled BOOLEAN DEFAULT TRUE,
    api_key_custom TEXT,
    query_rate_limit INT DEFAULT 100,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. 계정별 개인화 설정 및 포트폴리오 (user_settings)
CREATE TABLE IF NOT EXISTS public.user_settings (
    user_id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
    default_watchlist JSONB DEFAULT '[]'::jsonb,
    favorite_market TEXT DEFAULT 'ALL',
    custom_notes TEXT DEFAULT '',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==============================================================================
-- 🔒 RLS (Row Level Security, 행 수준 보안) 활성화 및 정책 정의
-- ==============================================================================

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.access_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_controls ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY;

-- 관리자 여부 확인 헬퍼 함수
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM public.profiles
        WHERE id = auth.uid() AND role = 'admin' AND status = 'approved'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- [profiles RLS]
-- 일반 사용자는 본인 프로필만 조회 가능, 관리자는 전체 조회/수정 가능
CREATE POLICY "Users can view own profile" 
    ON public.profiles FOR SELECT 
    USING (auth.uid() = id OR public.is_admin());

CREATE POLICY "Admin can update profiles" 
    ON public.profiles FOR UPDATE 
    USING (public.is_admin());

-- [access_logs RLS]
-- 사용자는 자신의 로그인 로그 삽입 가능, 읽기는 본인 또는 관리자만 가능
CREATE POLICY "Users can insert own log" 
    ON public.access_logs FOR INSERT 
    WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users and admin can read logs" 
    ON public.access_logs FOR SELECT 
    USING (auth.uid() = user_id OR public.is_admin());

-- [api_controls RLS]
-- 본인은 읽기만 가능(상태 확인용), 수정 및 제어는 오직 관리자만 가능
CREATE POLICY "Users can view own api controls" 
    ON public.api_controls FOR SELECT 
    USING (auth.uid() = user_id OR public.is_admin());

CREATE POLICY "Admin can modify api controls" 
    ON public.api_controls FOR ALL 
    USING (public.is_admin());

-- [user_settings RLS]
-- 철저한 개인 소유 격리: 오직 본인만 읽고 쓸 수 있음
CREATE POLICY "Users manage own settings" 
    ON public.user_settings FOR ALL 
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- 신규 가입 시 기본 레코드 자동 생성 트리거
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    -- 첫 가입자이거나 특정 지정자 외에는 기본 pending
    INSERT INTO public.profiles (id, email, role, status)
    VALUES (NEW.id, NEW.email, 'user', 'pending');
    
    INSERT INTO public.api_controls (user_id, allow_external_query, api_key_enabled)
    VALUES (NEW.id, FALSE, FALSE); -- 승인 전까지 외부조회 및 API 비활성화

    INSERT INTO public.user_settings (user_id)
    VALUES (NEW.id);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
