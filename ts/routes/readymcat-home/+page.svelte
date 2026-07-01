<!--
Copyright: Ankitects Pty Ltd and contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import type { PageData } from "./$types";
    import Home from "./Home.svelte";

    export let data: PageData;
</script>

<Home
    points={data.points}
    pointsError={data.pointsError}
    status={data.status}
    statusError={data.statusError}
    generatedAt={data.generatedAt}
/>
