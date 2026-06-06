import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import FileConflictDialog from '../blackboard/FileConflictDialog.vue'

const i18nMock = {
  global: {
    plugins: [],
    mocks: {
      $t: (key: string) => key,
    },
    stubs: {
      Button: { template: '<button><slot /></button>', props: ['variant', 'size', 'disabled'] },
      Teleport: { template: '<div><slot /></div>' },
    },
  },
}

describe('FileConflictDialog', () => {
  it('emits cancel when backdrop clicked', async () => {
    const wrapper = mount(FileConflictDialog, {
      ...i18nMock,
      props: {
        open: true,
        fileName: 'test.pdf',
        newSize: 1024,
      },
    })

    const backdrop = wrapper.find('.absolute.inset-0.bg-black\\/50')
    if (backdrop.exists()) {
      await backdrop.trigger('click')
      expect(wrapper.emitted('resolve')?.[0]).toEqual(['cancel'])
    }
  })

  it('emits keep_both when button clicked', async () => {
    const wrapper = mount(FileConflictDialog, {
      ...i18nMock,
      props: {
        open: true,
        fileName: 'test.pdf',
        newSize: 2048,
        existingSize: 1024,
        existingDate: '2026-05-30',
      },
    })

    const buttons = wrapper.findAll('button')
    const keepBothBtn = buttons.find(b => b.text().includes('upload.actions.keep_both'))
    if (keepBothBtn) {
      await keepBothBtn.trigger('click')
      expect(wrapper.emitted('resolve')?.[0]).toEqual(['keep_both'])
    }
  })

  it('requires double click for overwrite', async () => {
    const wrapper = mount(FileConflictDialog, {
      ...i18nMock,
      props: {
        open: true,
        fileName: 'test.pdf',
        newSize: 2048,
      },
    })

    const buttons = wrapper.findAll('button')
    const overwriteBtn = buttons.find(b => b.text().includes('upload.actions.overwrite'))
    if (overwriteBtn) {
      await overwriteBtn.trigger('click')
      expect(wrapper.emitted('resolve')).toBeUndefined()

      await overwriteBtn.trigger('click')
      expect(wrapper.emitted('resolve')?.[0]).toEqual(['overwrite'])
    }
  })

  it('does not render when open is false', () => {
    const wrapper = mount(FileConflictDialog, {
      ...i18nMock,
      props: {
        open: false,
        fileName: 'test.pdf',
      },
    })

    expect(wrapper.find('.fixed').exists()).toBe(false)
  })
})
