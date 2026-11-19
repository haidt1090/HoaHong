import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import { definePreset } from '@primeuix/themes'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'
import App from './App.vue'
import router from './router'
import '@/styles/main.css'
import 'primeicons/primeicons.css'

const ClinicPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#e6f2f0',
      100: '#c0ddd9',
      200: '#96c8c0',
      300: '#6cb2a7',
      400: '#4da195',
      500: '#0a7c6e',
      600: '#097064',
      700: '#086b5e',
      800: '#065448',
      900: '#043b33',
      950: '#022019',
    },
  },
})

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(PrimeVue, {
  theme: {
    preset: ClinicPreset,
    options: {
      darkModeSelector: '.dark-mode',
    },
  },
})
app.use(ToastService)
app.use(ConfirmationService)

app.mount('#app')
