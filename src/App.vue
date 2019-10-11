<template>
  <div>
    <v-app-bar color="deep-purple accent-4" dark>
      <v-app-bar-nav-icon></v-app-bar-nav-icon>

      <v-toolbar-title>Facebook Bdays</v-toolbar-title>
    </v-app-bar>

    <v-card max-width="500" class="mx-auto middle">
      <v-card-title>Facebook Login</v-card-title>
      <v-card-text>
        <v-text-field label="Email/Phone" v-model="email"></v-text-field>
        <v-text-field label="Password" type="password" v-model="pass"></v-text-field>
      </v-card-text>
      <v-card-actions>
        <v-btn text @click="getCalendar(email, pass)">Log In</v-btn>
      </v-card-actions>
    </v-card>
  </div>
</template>

<script>
import axios from 'axios';

export default {
  data() {
    return {
      email: '',
      pass: ''
    };
  },
  methods: {
    async getCalendar(email, pass) {
      const res = await axios.post('http://localhost:5000', { email, pass });
    }
  }
};
</script>

<style scoped>
.middle {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}
</style>