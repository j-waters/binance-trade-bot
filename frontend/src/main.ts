import { createApp } from "vue";
import App from "./App.vue";
import VueApexCharts from "vue3-apexcharts";

import "bulma/bulma.sass";

import VueSocketIOExt from "vue-socket.io-extended";
import { io } from "socket.io-client";

const socket = io("localhost:5123/frontend");

createApp(App)
  .use(VueApexCharts)
  .use(VueSocketIOExt, socket)
  .mount("#app");
