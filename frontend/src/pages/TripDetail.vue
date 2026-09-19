<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getJSON } from '../api'
const route = useRoute()
const item = ref(null)
const stations = ref([])
const err = ref('')
const nameOf = (code) => stations.value.find(s => s.code === code)?.name || code
onMounted(async () => {
  try {
    item.value = await getJSON(`/api/history/${route.params.id}`)
    stations.value = (await getJSON('/api/stations')).items
  } catch (e) {
    err.value = e.message
  }
})
</script>
<template>
  <div class="page"><h1>记录 #{{ route.params.id }}</h1>
    <div v-if="err" class="panel" style="color:#ff8080">{{ err }}</div>
    <div v-if="item" class="panel">
      <p>{{ item.kind === 'roundtrip' ? (item.result.direction === 'outbound' ? '去程' : '返程') : '单程' }}
         · {{ item.created_at }}</p>
      <!-- 打开去程只见去程途经：本记录只含本侧路径 -->
      <p v-if="item.result.path">途经：{{ item.result.path.map(nameOf).join(' → ') }}</p>
      <p v-if="item.result.reachable">
        {{ item.result.start }} → {{ item.result.end }}：{{ item.result.hops }} 站 ·
        票价 <span class="hero-num">¥{{ item.result.fare }}</span>
      </p>
      <p v-else class="muted">不可达</p>
      <p v-if="item.result.total_fare != null" class="muted">该往返合计 ¥{{ item.result.total_fare }}</p>
      <p v-if="item.pair_id">
        对侧记录：<router-link :to="`/history/${item.pair_id}`">#{{ item.pair_id }}</router-link>
      </p>
      <p><router-link to="/history">返回记录列表</router-link></p>
    </div>
  </div>
</template>
