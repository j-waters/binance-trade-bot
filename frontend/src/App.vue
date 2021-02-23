<template>
  <div>
    <scout-graphs
      :histories="scoutHistory"
    ></scout-graphs>
  </div>
</template>

<script lang="ts">
import { defineComponent } from "vue";
import api from "@/api";
import { groupBy } from "@/util";
import ScoutGraphs from "@/components/ScoutGraphs.vue";
import { Coin, ScoutLogEntry, ScoutLogsGrouped, Update } from "@/models";

export default defineComponent({
  name: "App",
  components: {
    ScoutGraphs
  },
  data() {
    return {
      scoutHistory: {} as ScoutLogsGrouped,
      currentCoin: null as Coin | null
    };
  },
  created() {
    api.get<ScoutLogEntry[]>("scouting_history").then(result => {
      this.scoutHistory = groupBy(result.data, entry => entry.to_coin.symbol);
    });

    api.get<Coin>("current_coin").then(result => {
      this.currentCoin = result.data;
    });

    this.$socket.$subscribe("update", (payload: Update<unknown>) => {
      switch (payload.table) {
        case "scout_history":
          const entry = payload.data as ScoutLogEntry;
          this.scoutHistory[entry.to_coin.symbol].push(entry);
          break;
      }
    });
  },
  unmounted() {
    this.$socket.$unsubscribe("update");
  }
});
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  margin-top: 60px;
}
</style>
