// Connection settings for the annotation database (see README.md, "Coordinator setup").
// The Supabase project URL and its publishable/anon key are designed to be public:
// all access goes through the pha_* functions, which check each annotator's code.
// Never put a service_role / secret key here.
window.PHA_CONFIG = {
  "supabaseUrl": "https://mlukkrctswzdaysxlhnf.supabase.co",
  "supabaseKey": "sb_publishable_m94m8acnP3cRfs_Yqd9CEg_8XvLNMpa"
};
