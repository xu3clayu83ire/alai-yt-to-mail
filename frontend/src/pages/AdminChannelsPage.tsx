/**
 * 管理員頻道管理頁面
 * 顯示全表頻道資料，支援新增、inline 修改與刪除操作
 * 此頁面不使用 Layout.tsx，採用獨立的管理後台 UI 風格，與 AdminSubscriptionsPage 一致
 * 刪除頻道時後端會同時取消訂閱並發送通知，需顯示受影響訂閱數
 * 401/403 錯誤表示 admin JWT 過期，自動清除 token 並跳轉至登入頁
 */

import { useState, useEffect, useCallback } from 'react';
import type { ReactElement } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import axios from 'axios';
import {
  adminListChannels,
  adminCreateChannel,
  adminUpdateChannel,
  adminDeleteChannel,
} from '../api/adminChannels';
import { removeAdminToken } from '../utils/storage';
import type { ChannelItem } from '../types';

/** 新增頻道表單 schema */
const createChannelSchema = z.object({
  channel_id: z.string().min(1, '請輸入 Channel ID'),
  channel_name: z.string().min(1, '請輸入頻道名稱'),
  channel_url: z.string().url('請輸入有效的 URL 格式'),
});

/** inline 修改表單 schema（channel_id 不可修改）*/
const editChannelSchema = z.object({
  channel_name: z.string().min(1, '請輸入頻道名稱'),
  channel_url: z.string().url('請輸入有效的 URL 格式'),
});

type CreateChannelFormData = z.infer<typeof createChannelSchema>;
type EditChannelFormData = z.infer<typeof editChannelSchema>;

/**
 * 管理員頻道管理頁面狀態型別
 * editingChannelId 追蹤正在 inline 編輯的頻道，null 表示無編輯中
 * deletingChannelId 追蹤正在進行刪除操作的頻道，避免重複點擊
 */
interface AdminChannelsPageState {
  channels: ChannelItem[];
  isLoading: boolean;
  error: string | null;
  deletingChannelId: string | null;
  editingChannelId: string | null;
  deleteSuccessMessage: string | null;
  createError: string | null;
  editError: string | null;
}

/**
 * inline 修改子元件 Props
 * 將編輯表單抽取為獨立元件，方便使用獨立的 react-hook-form 實例
 */
interface InlineEditRowProps {
  channel: ChannelItem;
  onSave: (channelId: string, data: EditChannelFormData) => Promise<void>;
  onCancel: () => void;
  isSaving: boolean;
  editError: string | null;
}

/**
 * 頻道 inline 編輯列元件
 * 顯示可編輯的 channel_name 與 channel_url 欄位，channel_id 顯示為唯讀
 * 使用獨立的 react-hook-form 實例確保編輯狀態不與新增表單衝突
 */
function InlineEditRow({
  channel,
  onSave,
  onCancel,
  isSaving,
  editError,
}: InlineEditRowProps): ReactElement {
  const editForm = useForm<EditChannelFormData>({
    resolver: zodResolver(editChannelSchema),
    defaultValues: {
      channel_name: channel.channel_name,
      channel_url: channel.channel_url,
    },
  });

  return (
    <tr className="bg-blue-50">
      {/* 頻道名稱（可編輯）*/}
      <td className="px-4 py-2">
        <input
          type="text"
          {...editForm.register('channel_name')}
          className="w-full border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {editForm.formState.errors.channel_name && (
          <p className="text-red-500 text-xs mt-0.5">
            {editForm.formState.errors.channel_name.message}
          </p>
        )}
      </td>
      {/* Channel ID（唯讀）*/}
      <td className="px-4 py-2 text-gray-500 font-mono text-xs">{channel.channel_id}</td>
      {/* URL（可編輯）*/}
      <td className="px-4 py-2">
        <input
          type="text"
          {...editForm.register('channel_url')}
          className="w-full border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {editForm.formState.errors.channel_url && (
          <p className="text-red-500 text-xs mt-0.5">
            {editForm.formState.errors.channel_url.message}
          </p>
        )}
        {editError && (
          <p className="text-red-500 text-xs mt-0.5">{editError}</p>
        )}
      </td>
      {/* 建立時間（唯讀）*/}
      <td className="px-4 py-2 text-gray-500 text-xs font-mono">{channel.created_at}</td>
      {/* 操作按鈕 */}
      <td className="px-4 py-2">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void editForm.handleSubmit((data) => onSave(channel.channel_id, data))()}
            disabled={isSaving}
            className="bg-blue-600 text-white text-xs px-3 py-1.5 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSaving ? '儲存中...' : '儲存'}
          </button>
          <button
            type="button"
            onClick={onCancel}
            disabled={isSaving}
            className="border border-gray-300 text-gray-700 text-xs px-3 py-1.5 rounded hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            取消
          </button>
        </div>
      </td>
    </tr>
  );
}

/**
 * 管理員頻道管理頁面元件
 * 頁面載入時自動查詢全表，支援新增、inline 修改與確認刪除操作
 */
export function AdminChannelsPage(): ReactElement {
  const navigate = useNavigate();

  const [state, setState] = useState<AdminChannelsPageState>({
    channels: [],
    isLoading: true,
    error: null,
    deletingChannelId: null,
    editingChannelId: null,
    deleteSuccessMessage: null,
    createError: null,
    editError: null,
  });
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  /** 新增頻道表單 */
  const createForm = useForm<CreateChannelFormData>({
    resolver: zodResolver(createChannelSchema),
    defaultValues: {
      channel_id: '',
      channel_name: '',
      channel_url: '',
    },
  });

  /**
   * 處理 API 認證錯誤
   * 收到 AUTH_EXPIRED 錯誤時清除 admin token 並跳轉至登入頁
   * 此函式避免在多個 catch 區塊重複撰寫相同的登出邏輯
   */
  const handleAuthExpired = useCallback(
    (error: unknown): void => {
      if (error instanceof Error && error.message === 'AUTH_EXPIRED') {
        removeAdminToken();
        navigate('/admin/login', { replace: true });
      }
    },
    [navigate]
  );

  /**
   * 載入頻道列表
   * 頁面初次載入與各操作成功後均需重新 fetch，確保顯示最新資料
   */
  const loadChannels = useCallback(async (): Promise<void> => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const data = await adminListChannels();
      setState((prev) => ({ ...prev, channels: data, isLoading: false }));
    } catch (error: unknown) {
      handleAuthExpired(error);
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: '載入失敗，請重新整理',
      }));
    }
  }, [handleAuthExpired]);

  /** 頁面首次載入時查詢全表 */
  useEffect(() => {
    void loadChannels();
  }, [loadChannels]);

  /**
   * 處理新增頻道
   * 409 衝突表示 channel_id 已存在，顯示明確的錯誤訊息而非通用提示
   * 成功後重置表單並重新載入列表
   */
  const handleCreate = async (data: CreateChannelFormData): Promise<void> => {
    setState((prev) => ({ ...prev, createError: null, deleteSuccessMessage: null }));
    try {
      await adminCreateChannel(data);
      createForm.reset({ channel_id: '', channel_name: '', channel_url: '' });
      await loadChannels();
    } catch (error: unknown) {
      handleAuthExpired(error);
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        setState((prev) => ({ ...prev, createError: '此頻道 ID 已存在' }));
      } else if (!(error instanceof Error && error.message === 'AUTH_EXPIRED')) {
        setState((prev) => ({ ...prev, createError: '新增失敗，請重試' }));
      }
    }
  };

  /**
   * 處理 inline 修改儲存
   * 成功後結束編輯狀態並重新載入列表
   */
  const handleSaveEdit = async (
    channelId: string,
    data: EditChannelFormData
  ): Promise<void> => {
    setIsSavingEdit(true);
    setState((prev) => ({ ...prev, editError: null, deleteSuccessMessage: null }));
    try {
      await adminUpdateChannel(channelId, data);
      setState((prev) => ({ ...prev, editingChannelId: null }));
      await loadChannels();
    } catch (error: unknown) {
      handleAuthExpired(error);
      if (!(error instanceof Error && error.message === 'AUTH_EXPIRED')) {
        setState((prev) => ({ ...prev, editError: '儲存失敗，請重試' }));
      }
    } finally {
      setIsSavingEdit(false);
    }
  };

  /**
   * 處理刪除頻道
   * 顯示詳細確認提示，告知刪除後將取消所有相關訂閱並寄通知
   * 成功後顯示受影響訂閱數並重新載入列表
   */
  const handleDelete = async (channel: ChannelItem): Promise<void> => {
    const confirmed = window.confirm(
      `刪除後將同時取消所有訂閱此頻道的用戶並發送通知信，確定刪除嗎？\n\n頻道：${channel.channel_name}`
    );
    if (!confirmed) return;

    setState((prev) => ({
      ...prev,
      deletingChannelId: channel.channel_id,
      deleteSuccessMessage: null,
    }));
    try {
      const result = await adminDeleteChannel(channel.channel_id);
      setState((prev) => ({
        ...prev,
        deletingChannelId: null,
        deleteSuccessMessage: `已刪除，共取消 ${result.cancelled_subscriptions} 筆訂閱`,
      }));
      await loadChannels();
    } catch (error: unknown) {
      setState((prev) => ({ ...prev, deletingChannelId: null }));
      handleAuthExpired(error);
      if (!(error instanceof Error && error.message === 'AUTH_EXPIRED')) {
        alert('刪除失敗，請重試');
      }
    }
  };

  /**
   * 管理員登出：清除 admin token 並跳轉至 /admin/login
   * 使用 replace 避免回上一頁繞過登入保護
   */
  const handleLogout = (): void => {
    removeAdminToken();
    navigate('/admin/login', { replace: true });
  };

  const location = useLocation();
  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 頁首：標題 + 導覽連結 + 登出按鈕 */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div>
              <h1 className="text-xl font-bold text-gray-900">DailyCast Admin</h1>
            </div>
            <nav className="flex items-center gap-4">
              <Link
                to="/admin/subscriptions"
                className={`text-sm font-medium transition-colors ${
                  isActive('/admin/subscriptions') ? 'text-blue-600' : 'text-gray-500 hover:text-gray-900'
                }`}
              >
                訂閱列表
              </Link>
              <Link
                to="/admin/channels"
                className={`text-sm font-medium transition-colors ${
                  isActive('/admin/channels') ? 'text-blue-600' : 'text-gray-500 hover:text-gray-900'
                }`}
              >
                頻道管理
              </Link>
            </nav>
          </div>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-md px-3 py-1.5 hover:bg-gray-50 transition-colors"
          >
            登出
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* 成功訊息 */}
        {state.deleteSuccessMessage && (
          <div className="bg-green-50 border border-green-200 rounded-md px-4 py-3 mb-4">
            <p className="text-green-700 text-sm">{state.deleteSuccessMessage}</p>
          </div>
        )}

        {/* 錯誤訊息 */}
        {state.error && (
          <div className="bg-red-50 border border-red-200 rounded-md px-4 py-3 mb-4">
            <p className="text-red-600 text-sm">{state.error}</p>
          </div>
        )}

        {/* 新增頻道表單 */}
        <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
          <h2 className="text-base font-semibold text-gray-800 mb-3">新增頻道</h2>
          <form
            onSubmit={createForm.handleSubmit((data) => void handleCreate(data))}
            className="space-y-3"
          >
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {/* Channel ID */}
              <div>
                <label
                  htmlFor="create-channel-id"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Channel ID
                </label>
                <input
                  id="create-channel-id"
                  type="text"
                  {...createForm.register('channel_id')}
                  placeholder="UCxxxxxxxxxxxxxx"
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {createForm.formState.errors.channel_id && (
                  <p className="text-red-500 text-xs mt-1">
                    {createForm.formState.errors.channel_id.message}
                  </p>
                )}
              </div>

              {/* 頻道名稱 */}
              <div>
                <label
                  htmlFor="create-channel-name"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  頻道名稱
                </label>
                <input
                  id="create-channel-name"
                  type="text"
                  {...createForm.register('channel_name')}
                  placeholder="頻道顯示名稱"
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {createForm.formState.errors.channel_name && (
                  <p className="text-red-500 text-xs mt-1">
                    {createForm.formState.errors.channel_name.message}
                  </p>
                )}
              </div>

              {/* 頻道 URL */}
              <div>
                <label
                  htmlFor="create-channel-url"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  頻道 URL
                </label>
                <input
                  id="create-channel-url"
                  type="text"
                  {...createForm.register('channel_url')}
                  placeholder="https://www.youtube.com/@..."
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {createForm.formState.errors.channel_url && (
                  <p className="text-red-500 text-xs mt-1">
                    {createForm.formState.errors.channel_url.message}
                  </p>
                )}
              </div>
            </div>

            {state.createError && (
              <div className="bg-red-50 border border-red-200 rounded-md px-3 py-2">
                <p className="text-red-600 text-sm">{state.createError}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={createForm.formState.isSubmitting}
              className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {createForm.formState.isSubmitting ? '新增中...' : '新增頻道'}
            </button>
          </form>
        </div>

        {/* 頻道列表表格 */}
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          {state.isLoading ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-gray-500 text-sm">載入中...</p>
            </div>
          ) : state.channels.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-gray-500 text-sm">尚無頻道資料</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">頻道名稱</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">Channel ID</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">URL</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">建立時間 (UTC)</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {state.channels.map((channel) =>
                    state.editingChannelId === channel.channel_id ? (
                      <InlineEditRow
                        key={channel.channel_id}
                        channel={channel}
                        onSave={handleSaveEdit}
                        onCancel={() =>
                          setState((prev) => ({
                            ...prev,
                            editingChannelId: null,
                            editError: null,
                          }))
                        }
                        isSaving={isSavingEdit}
                        editError={state.editError}
                      />
                    ) : (
                      <tr key={channel.channel_id} className="hover:bg-gray-50 transition-colors">
                        {/* 頻道名稱 */}
                        <td className="px-4 py-3 text-gray-900 font-medium">
                          {channel.channel_name}
                        </td>
                        {/* Channel ID */}
                        <td className="px-4 py-3 text-gray-600 font-mono text-xs">
                          {channel.channel_id}
                        </td>
                        {/* URL（可點擊連結）*/}
                        <td className="px-4 py-3">
                          <a
                            href={channel.channel_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 hover:underline text-xs"
                          >
                            {channel.channel_url}
                          </a>
                        </td>
                        {/* 建立時間（UTC 格式）*/}
                        <td className="px-4 py-3 text-gray-700 text-xs font-mono">
                          {channel.created_at}
                        </td>
                        {/* 操作按鈕 */}
                        <td className="px-4 py-3">
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={() =>
                                setState((prev) => ({
                                  ...prev,
                                  editingChannelId: channel.channel_id,
                                  editError: null,
                                  deleteSuccessMessage: null,
                                }))
                              }
                              disabled={
                                state.deletingChannelId === channel.channel_id ||
                                state.editingChannelId !== null
                              }
                              className="bg-yellow-500 text-white text-xs px-3 py-1.5 rounded hover:bg-yellow-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                              修改
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleDelete(channel)}
                              disabled={
                                state.deletingChannelId === channel.channel_id ||
                                state.editingChannelId !== null
                              }
                              className="bg-red-600 text-white text-xs px-3 py-1.5 rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                              {state.deletingChannelId === channel.channel_id
                                ? '刪除中...'
                                : '刪除'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* 資料筆數摘要 */}
        {!state.isLoading && state.channels.length > 0 && (
          <p className="text-gray-500 text-xs mt-3 text-right">
            共 {state.channels.length} 個頻道
          </p>
        )}
      </main>
    </div>
  );
}
