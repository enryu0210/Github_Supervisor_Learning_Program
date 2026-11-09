// lib/data/index.ts
// 화면은 이 파일의 DataSource 함수만 호출한다.
// 샘플 JSON이나 Supabase를 화면에서 직접 부르지 않는다.
//
// 구현체 2개:
//   - mockSource      (samples/*.json, 11/9~11/16)
//   - supabaseSource  (DB 뷰, 11/19~20 이남주와 함께 추가)
//
// 아래 반환 타입의 필드 이름은 DB 뷰 컬럼과 같게 맞춘다(snake_case).
// 이남주의 뷰 컬럼 목록(11/16 전후)이 나오면 이 파일을 기준으로 맞춰 본다.

import type {
  EventAction,
  EventSource,
  GitCoachEvent,
  RuleId,
  Severity,
} from "@/types/event";

/* ------------------------------------------------------------------ */
/* 공통 입력                                                            */
/* ------------------------------------------------------------------ */

/** 기간. 둘 다 ISO 8601. from 포함, to 미포함. */
export type Range = {
  from: string;
  to: string;
};

/**
 * 타임라인·개요 차트가 함께 쓰는 필터.
 * 필터 상태는 URL 쿼리 한 곳에 두고, 이 객체로 변환해 넘긴다.
 * 배열이 비어 있거나 없으면 "전체"로 본다.
 */
export type EventFilter = {
  range?: Range;
  members?: string[];
  ruleIds?: RuleId[];
  sources?: EventSource[];
  severities?: Severity[];
  actions?: EventAction[];
  repo?: string;
};

/* ------------------------------------------------------------------ */
/* 반환 타입                                                            */
/* ------------------------------------------------------------------ */

/**
 * 규칙별 위반 집계 ( / 개요의 규칙별 위반 비율, /me 의 자주 틀린 규칙 TOP ).
 * 위반 수는 VIOLATION_ACTIONS(allowed·guided·blocked·detected)만 센다.
 */
export type RuleStat = {
  rule_id: RuleId;
  severity: Severity;
  violation_count: number; // allowed + guided + blocked + detected
  allowed_count: number; // 알면서도 실행
  guided_count: number;
  blocked_count: number;
  detected_count: number;
  ratio: number; // 0~1, 같은 필터 안 전체 위반 대비 비율
};

/**
 * 가이드 학습 지표 (가이드 완료율).
 * completed·stopped는 related_event_id로 원래 guided 이벤트와 연결해 센다.
 */
export type GuideStat = {
  rule_id: RuleId;
  guided_count: number;
  completed_count: number;
  stopped_count: number;
  in_progress_count: number; // guided인데 아직 완료·중단 기록이 없는 것
  completion_rate: number; // completed / guided, guided가 0이면 0
};

/** 멤버별 활동 ( / 개요의 멤버별 PR·리뷰 분포 ). */
export type MemberActivity = {
  member: string; // github_login
  prs_opened: number;
  prs_merged: number;
  reviews_given: number;
  violation_count: number;
};

/** 방치된 PR ( / 개요 ). 기준 일수는 DB 뷰 쪽과 맞춘다. */
export type StalePr = {
  repo: string;
  pr_number: number;
  title: string;
  author: string;
  opened_at: string;
  last_activity_at: string;
  idle_days: number;
  url: string;
};

/**
 * 복습 퀴즈 ( /quiz ).
 * 퀴즈는 웹에서 만들지 않는다. CLI·watcher(Ollama 쪽)가 생성해 DB에 저장한 것을 보여 주기만 한다.
 * 출제 근거는 주로 allowed·guide_stopped 이벤트다.
 */
export type Quiz = {
  id: string;
  member: string;
  rule_id: RuleId;
  source_event_id: string | null; // 출제 근거 이벤트
  question: string;
  choices: string[];
  answer_index: number;
  explanation: string;
  created_at: string;
};

/** 퀴즈 풀이 기록 (attempts). v0.1은 읽기 전용이라 조회만 한다. */
export type QuizAttempt = {
  id: string;
  quiz_id: string;
  member: string;
  selected_index: number;
  is_correct: boolean;
  attempted_at: string;
};

/* ------------------------------------------------------------------ */
/* 데이터 소스 인터페이스                                                */
/* ------------------------------------------------------------------ */

export interface DataSource {
  /** 위반 타임라인 ( /events ). 최신순. */
  getEvents(filter?: EventFilter): Promise<GitCoachEvent[]>;

  /** 규칙별 위반 집계. /me 에서는 filter.members = [현재 사용자]로 부른다. */
  getRuleStats(filter?: EventFilter): Promise<RuleStat[]>;

  /** 가이드 완료율 등 학습 지표. */
  getGuideStats(filter?: EventFilter): Promise<GuideStat[]>;

  /** 멤버별 PR·리뷰·위반 분포. */
  getMemberActivity(range: Range): Promise<MemberActivity[]>;

  /** 방치된 PR 목록. */
  getStalePrs(): Promise<StalePr[]>;

  /** 내 퀴즈 목록. */
  getQuizzes(member: string): Promise<Quiz[]>;

  /** 내 풀이 기록. */
  getQuizAttempts(member: string): Promise<QuizAttempt[]>;
}

/*
 * 구현체 선택은 구현체를 추가할 때 이 아래에 둔다. 예:
 *
 *   import { mockSource } from "./mock";
 *   import { supabaseSource } from "./supabase";
 *   export const data: DataSource =
 *     process.env.NEXT_PUBLIC_DATA_SOURCE === "supabase" ? supabaseSource : mockSource;
 *
 * supabaseSource는 anon 키와 로그인 사용자 토큰만 쓴다. service_role 키는 절대 넣지 않는다.
 */