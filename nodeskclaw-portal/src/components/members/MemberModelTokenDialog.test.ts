import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MemberModelTokenDialog from './MemberModelTokenDialog.vue'

const { store } = vi.hoisted(() => ({
  store: {
    fetchMemberTokens: vi.fn(),
    fetchNewApiGroups: vi.fn(),
    createMemberToken: vi.fn(),
    bindMemberToken: vi.fn(),
    updateMemberToken: vi.fn(),
    deleteMemberToken: vi.fn(),
    revealMemberToken: vi.fn(),
    retryRevokeMemberToken: vi.fn(),
    closeLocalMemberToken: vi.fn(),
    refreshMemberTokenModels: vi.fn(),
    saveMemberTokenModels: vi.fn(),
  },
}))

vi.mock('@/stores/memberManagement', () => ({
  useMemberManagementStore: () => store,
}))

vi.mock('@/i18n/error', () => ({
  resolveApiErrorMessage: (error: { response?: { data?: { message_key?: string } } }, fallback = '') =>
    error?.response?.data?.message_key || fallback,
}))

const InputStub = {
  props: ['modelValue', 'disabled', 'type', 'placeholder'],
  emits: ['update:modelValue'],
  template: '<input :value="modelValue" :disabled="disabled" :type="type || \'text\'" @input="$emit(\'update:modelValue\', $event.target.value)" />',
}

const SelectStub = {
  props: ['modelValue', 'options', 'disabled'],
  emits: ['update:modelValue'],
  template: '<select :value="modelValue" :disabled="disabled" @change="$emit(\'update:modelValue\', $event.target.value)"><option v-for="item in options" :key="item.value" :value="item.value">{{ item.label }}</option></select>',
}

function mountDialog() {
  return mount(MemberModelTokenDialog, {
    props: {
      open: true,
      canManage: true,
      member: {
        id: 'm1',
        user_id: 'u1',
        user_name: 'Alice',
        user_email: 'alice@example.com',
        role: 'member',
        is_active: true,
      },
    },
    global: {
      stubs: {
        Input: InputStub,
        CustomSelect: SelectStub,
        Button: { template: '<button :disabled="disabled"><slot /></button>', props: ['disabled', 'variant', 'size'] },
        Label: { template: '<label><slot /></label>' },
      },
    },
  })
}

describe('MemberModelTokenDialog', () => {
  beforeEach(() => {
    store.fetchMemberTokens.mockReset()
    store.fetchNewApiGroups.mockReset()
    store.createMemberToken.mockReset()
    store.bindMemberToken.mockReset()
    store.fetchMemberTokens.mockResolvedValue([])
    store.fetchNewApiGroups.mockResolvedValue({
      items: [{ value: 'default', label: 'default' }],
      modelBaseUrl: 'http://new-api.example/v1',
    })
  })

  it('lets the admin edit the auto-created token name', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    const inputs = wrapper.findAll('input')
    const name = inputs.find(input => (input.element as HTMLInputElement).value === 'alice')
    expect(name).toBeTruthy()
    expect((name!.element as HTMLInputElement).disabled).toBe(false)
    expect(wrapper.text()).toContain('memberManagement.modelTokenNameHint')
  })

  it('binds without a base url field, model text, or plaintext', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    const mode = wrapper.findAll('select')[1]
    await mode.setValue('bind')
    await flushPromises()
    expect(wrapper.text()).toContain('memberManagement.modelTokenBind')
    expect(wrapper.text()).toContain('memberManagement.modelTokenBindWarning')
    expect(wrapper.text()).not.toContain('memberManagement.modelTokenModels')
    const url = wrapper.find('input[disabled]')
    expect((url.element as HTMLInputElement).value).toBe('http://new-api.example/v1')
    await wrapper.find('input[type="password"]').setValue('sk-entered')
    await wrapper.find('button').trigger('click')
    await flushPromises()
    expect(store.bindMemberToken).toHaveBeenCalledWith('m1', {
      provider: 'new-api',
      token_name: 'alice',
      token: 'sk-entered',
      is_default: true,
    })
    expect(store.createMemberToken).not.toHaveBeenCalled()
    expect(wrapper.text()).not.toContain('memberManagement.modelTokenPlaintextOnce')
  })

  it('keeps comma model text for deepseek', async () => {
    const wrapper = mountDialog()
    await flushPromises()
    await wrapper.find('select').setValue('deepseek')
    await flushPromises()
    expect(wrapper.text()).toContain('memberManagement.modelTokenModels')
  })

  it('shows both next steps when the token name conflicts', async () => {
    store.createMemberToken.mockRejectedValue({
      response: { data: { message_key: 'errors.member_token.name_conflict' } },
    })
    const wrapper = mountDialog()
    await flushPromises()
    await wrapper.find('button').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('errors.member_token.name_conflict')
    expect(store.bindMemberToken).not.toHaveBeenCalled()
  })
})
