<script setup>
import { computed, onMounted, ref } from 'vue'
import { getJSON, postJSON } from '../api'
const stations = ref([])
const start = ref('A1')
const end = ref('B2')
const persist = ref(true)
const out = ref(null)
const err = ref('')
onMounted(async () => { stations.value = (await getJSON('/api/stations')).items })
const nameOf = (code) => stations.value.find(s => s.code === code)?.name || code
// 返程自动对调：返程起点=去程终点，返程终点=去程起点
const returnStart = computed(() => end.value)
const returnEnd = computed(() => start.value)
const run = async () => {
  err.value = ''
  out.value = null
  try {
    out.value = await postJSON('/api/quote/roundtrip', {
      outbound_start: start.value,
      outbound_end: end.value,
      return_start: returnStart.value,
      return_end: returnEnd.value,
      persist: persist.value,
    })
  } catch (e) {
    err.value = e.message
  }
}
</script>
<template>
  <div class="page"><h1>往返联程票价</h1>
    <div class="panel">
      <div>去程
        <select v-model="start"><option v-for="s in stations" :key="s.code" :value="s.code">{{ s.name }}</option></select>
        →
        <select v-model="end"><option v-for="s in stations" :key="s.code" :value="s.code">{{ s.name }}</option></select>
      </div>
      <div class="muted" style="margin-top:0.5rem">返程（自动对调）
        <span class="auto-box">{{ nameOf(returnStart) }}</span>
        →
        <span class="auto-box">{{ nameOf(returnEnd) }}</span>
      </div>
      <label class="muted" style="display:block;margin-top:0.5rem">
        <input type="checkbox" v-model="persist"> 保存到记录
      </label>
      <button @click="run" style="margin-top:0.6rem">试算</button>
    </div>
    <div v-if="err" class="panel" style="color:#ff8080">{{ err }}</div>
    <div v-if="out && !out.reachable" class="panel">
      <p class="muted">不可达：去程或返程无可达路径，未保存任何记录。</p>
    </div>
    <div v-if="out && out.reachable" class="panel">
      <p>去程途经：{{ out.outbound.path.map(nameOf).join(' → ') }}（{{ out.outbound.hops }} 站 · ¥{{ out.outbound.fare }}）</p>
      <p>返程途经：{{ out.inbound.path.map(nameOf).join(' → ') }}（{{ out.inbound.hops }} 站 · ¥{{ out.inbound.fare }}）</p>
      <p>往返合计 <span class="hero-num">¥{{ out.total_fare }}</span></p>
      <p v-if="out.outbound_id" class="muted">
        已保存：去程 <router-link :to="`/history/${out.outbound_id}`">#{{ out.outbound_id }}</router-link>
        · 返程 <router-link :to="`/history/${out.inbound_id}`">#{{ out.inbound_id }}</router-link>
      </p>
      <p v-else class="muted">本次未保存。</p>
    </div>
  </div>
</template>
