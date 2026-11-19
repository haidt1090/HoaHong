// ===========================================================================
// Central keyboard-shortcut definitions (Sprint F2).
// All data-entry / employee-list shortcuts are declared here so they can be
// toggled, displayed in the "Phím tắt" modal and re-used without copy-paste.
// ===========================================================================

export interface ShortcutDefinition {
  /** Stable identifier used to reference this shortcut in code / config. */
  id: string
  /** Combo string, e.g. `Ctrl+S`, `Ctrl+Shift+Q`, `ArrowDown`. */
  combo: string
  /** Human-readable Vietnamese label of the action. */
  label: string
  /** Extra explanation shown in the shortcuts modal. */
  description?: string
  /** When false the shortcut is not registered and not listed. */
  enabled: boolean
}

export interface ShortcutGroup {
  /** Screen / section name (displayed as a heading in the modal). */
  group: string
  shortcuts: ShortcutDefinition[]
}

export const DATA_ENTRY_SHORTCUTS: ShortcutGroup[] = [
  {
    group: 'Nhập liệu',
    shortcuts: [
      {
        id: 'saveDept',
        combo: 'Ctrl+S',
        label: 'Lưu phòng ban hiện tại',
        description: 'Chỉ lưu khoa đang mở, không chuyển nhân viên.',
        enabled: true,
      },
      {
        id: 'saveAll',
        combo: 'Ctrl+Shift+S',
        label: 'Lưu tất cả rồi sang nhân viên kế',
        description: 'Lưu mọi khoa chưa lưu, rồi focus ô đầu của khoa đang mở trên NV tiếp theo.',
        enabled: true,
      },
      {
        id: 'saveAndNext',
        combo: 'Ctrl+Q',
        label: 'Lưu tất cả và chuyển nhân viên kế tiếp',
        description: 'Lưu mọi khoa chưa lưu, rồi focus ô đầu của khoa đang mở trên NV tiếp theo.',
        enabled: true,
      },
      {
        id: 'prevEmployee',
        combo: 'Ctrl+Shift+Q',
        label: 'Chuyển về nhân viên trước đó',
        enabled: true,
      },
      {
        id: 'switchDept',
        combo: 'Ctrl+1 … Ctrl+9',
        label: 'Chuyển đến phòng ban thứ 1 … 9',
        enabled: true,
      },
      {
        id: 'enterLastCell',
        combo: 'Enter',
        label: 'Tự động lưu khi nhấn Enter ở ô cuối',
        description: 'Chỉ áp dụng khi con trỏ đang ở ô nhập cuối cùng của phòng ban.',
        enabled: true,
      },
    ],
  },
]

export const EMPLOYEE_LIST_SHORTCUTS: ShortcutGroup[] = [
  {
    group: 'Danh sách nhân viên',
    shortcuts: [
      {
        id: 'focusSearch',
        combo: 'Ctrl+F',
        label: 'Đưa con trỏ vào ô tìm kiếm',
        enabled: true,
      },
      {
        id: 'moveSelection',
        combo: '↑ / ↓',
        label: 'Di chuyển lựa chọn giữa các nhân viên',
        enabled: true,
      },
      {
        id: 'openEmployee',
        combo: 'Enter',
        label: 'Mở nhân viên đang chọn',
        enabled: true,
      },
      {
        id: 'deleteEmployee',
        combo: 'Delete',
        label: 'Xóa nhân viên đang chọn (có xác nhận)',
        enabled: true,
      },
    ],
  },
]

/** Runtime knobs that are not tied to a single combo. */
export const SHORTCUT_CONFIG = {
  /** When true, pressing Enter in the last editable cell auto-saves that department. */
  autoSaveOnEnterLastCell: true,
}
