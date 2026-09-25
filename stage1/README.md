# V85x stage 1 — Linux en RAM, BusyBox et USB ACM + CDC-NCM

État au 25 septembre 2026 : **Linux 7.2.7 validé sur le dongle avec la série V853 v2 de février 2025**. Les 128 Mio passent deux tests complets sans cache/MMU. Le noyau démarre en RAM avec un gadget USB composite ACM + CDC-NCM : console BusyBox, bail DHCP pour le Mac, ping et SSH Dropbear par clé ont été vérifiés. Le portage précédent et ses preuves restent documentés plus bas ; les résultats 6.13 sont conservés dans `logs/network-*` et `logs/usb-shell-6.13.log`.

**État actuel de la flash : le 24 septembre 2026, à la demande explicite de l’utilisateur, la partition boot0 (premier Mio) a été sauvegardée puis effacée pour permettre le retour automatique en FEL.** La relecture confirme 1 Mio entièrement à `0xff` et les 3 Mio d’U-Boot strictement inchangés. Après `xfel reset`, FEL répond avec `ID=0x00188600`, scratchpad `0x00040400`. Le retour automatique en FEL après coupure physique est également confirmé le 25 septembre 2026. Le firmware d’origine ne peut plus démarrer tant que boot0 n’est pas restauré. Voir [sauvegarde et restauration](BOOT0-RECOVERY.md).

Le FES V0.16 atteignait la fin de son initialisation, mais les lectures mémoire bloquaient. Le pilote C V0.24 d’awboot fonctionne avec les paramètres du boot0 original ; voir [son adaptation SRAM](boot/awboot/README.md). Le chargement du boot0 natif à `0x20000` reste désactivé après un blocage pendant son transfert. Les essais antérieurs sont conservés dans [l’historique](EXPERIMENT-HISTORY.md).

## Sources et construction

- Linux [7.2.7](https://www.kernel.org/pub/linux/kernel/v7.x/), archive dans `downloads/` ; SHA-256 dans `downloads/SHA256SUMS`.
- `configs/linux-7.2.7-v853-patchew-v2.patch` est le rebasage de la [série V853 v2 de février 2025](https://patchew.org/linux/20250205125225.1152849-1-szemzo.andras@gmail.com/) sur Linux 7.2.7. Les patches 5 et 6 (PPU) sont déjà intégrés au noyau 7.2.7 ; les conflits des patches 1 et 7 ont été adaptés à ses API et à son schéma PHY. Le patch résultant a été rejoué sur les fichiers d’une archive 7.2.7 neuve et le noyau a compilé et démarré sur le dongle.
- `configs/sun8i-v851s-dongle-stage1-patchew-v2.dts` adapte le DTB du dongle à la nouvelle DTSI (oscillateur 24 MHz, nœuds VE/NPU/THS absents de cette version). Le patch précédent `configs/linux-7.2.7-v853-stage1.patch`, issu d’[awboot 5380c00f](https://github.com/szemzoa/awboot/tree/5380c00fc67c975433f25c57fb481aa2b91aebf8), reste conservé pour comparaison.
- Ajout local de `allwinner,sun8i-v853` à la liste des machines ARM (`configs/0001-v853-machine.patch`).
- BusyBox 1.37.0, statique ARM EABI hard-float. Accélérations SHA x86 désactivées pour cette compilation ARM.
- [Dropbear 2026.94](https://matt.ucc.asn.au/dropbear/dropbear.html), statique ARM, authentification par clé seulement. Une clé hôte et une clé cliente de développement sont conservées localement dans `out/ssh/` entre deux builds.
- [xfel 445e8aef](https://github.com/xboot/xfel/tree/445e8aefe6914c85817cc9bd1d201629364b0ec6), à placer dans `src/xfel` et à modifier avec `configs/0002-xfel-usb-timeout.patch` pour le test mémoire long.
- Le chemin matériel validé utilise le pilote DDR C d’awboot en SRAM. Les diagnostics antérieurs utilisent aussi un initialiseur extrait de xfel avec les 24 paramètres du boot0.
- Trampoline ARM minimal fondé sur le protocole de démarrage Linux et les registres V85x utilisés par awboot. Il préserve la DRAM, traite les caches et remet l’USB à zéro ; il ne reprend pas le chemin PSCI T113 du `main.c` actuel d’awboot.

La compilation Linux utilise un conteneur Debian ARM64 avec `arm-linux-gnueabihf-gcc`. Le build natif des petits programmes SRAM utilise `arm-none-eabi-gcc` sur macOS.

Depuis la racine du projet :

```sh
docker build -t v851s-stage1-builder stage1
docker run --rm --name v851s-stage1-build \
  -v "$PWD/stage1:/work" v851s-stage1-builder bash tools/build-linux.sh
bash stage1/tools/build-sram.sh
bash stage1/tools/build-awboot-ddr.sh
make -C stage1/src/xfel -j4
cp stage1/src/xfel/xfel stage1/tools/xfel
python3 stage1/tools/prepare-ddr.py stage1/boot/xfel-v851_v853.c \
  firmware-128MiB.bin stage1/out/ddr-stock.bin
```

`build-linux.sh` extrait automatiquement Linux 7.2.7 dans `src/patchew-v2/` si nécessaire, puis applique le patch V853 v2 et celui de la machine ARM. BusyBox et Dropbear doivent déjà être extraits dans `src/`. Pour repartir d’une extraction neuve :

```sh
tar -xjf stage1/downloads/busybox-1.37.0.tar.bz2 -C stage1/src
tar -xjf stage1/downloads/dropbear-2026.94.tar.bz2 -C stage1/src
git clone https://github.com/xboot/xfel.git stage1/src/xfel
git -C stage1/src/xfel checkout 445e8aefe6914c85817cc9bd1d201629364b0ec6
patch -d stage1/src/xfel -p1 < stage1/configs/0002-xfel-usb-timeout.patch
```

Les archives Linux 7.2.7, BusyBox 1.37.0 et Dropbear 2026.94 sont à obtenir avant ces commandes ; leurs SHA-256 figurent dans `downloads/SHA256SUMS`. Le dépôt Git exclut les sources téléchargées, les binaires construits, les clés SSH et le dump NAND. Les sauvegardes boot0/U-Boot restent locales : leur présence et leur somme SHA-256 doivent être contrôlées avant toute restauration.

Les options indispensables sont contrôlées avant compilation. MTD, SPI, MMC et les modules sont désactivés. Le système racine est un initramfs ; `/init` crée un gadget composite ACM + CDC-NCM, ouvre un shell sur `ttyGS0`, monte `lo`, donne `10.77.0.1/24` à `usb0`, démarre `udhcpd` puis Dropbear. DHCP attribue au Mac une adresse de `10.77.0.2` à `10.77.0.20`. Dropbear accepte seulement la clé `out/ssh/client_ed25519` ; la clé privée reste sur l’hôte. `CONFIG_COMPAT_32BIT_TIME` est requis par la libc ARM de Dropbear pour `select()`.

## Essais matériels, dans cet ordre

Ces commandes sont des opérations **RAM/SRAM uniquement**. Le test mémoire remplace le contenu volatile ; un retour au firmware d’origine nécessite un redémarrage. Ne pas les exécuter en parallèle avec un autre outil FEL.

```sh
python3 stage1/tools/ram-boot.py inspect
python3 stage1/tools/ram-boot.py ddr-awboot
python3 stage1/tools/ram-boot.py test-ram
python3 stage1/tools/ram-boot.py boot
```

`ddr-awboot` vérifie le chargement du pilote C à `0x28000`, l’exécute, puis vérifie trois régions DRAM distinctes. Le watchdog couvre son exécution ; sept attentes de registres sont bornées à 100 ms. `test-ram` effectue deux passes complètes, motifs adresse XOR masque et son complément, sur les 128 Mio avec cache de données/MMU désactivés. Il refuse de valider un résultat incomplet ou un mode CPU inattendu. Son résultat est dans `logs/ram-test-result.json`, puis `logs/ram-validated.json` en cas de succès.

`boot` exige la preuve du test et son marqueur encore présent en RAM. Chaque image envoyée est relue et comparée octet par octet. Les plages mémoire sont bornées. Le manifeste du dernier essai est dans `logs/last-boot-images.json`.

| Objet | Adresse | Borne |
| --- | --- | --- |
| Initialiseur DDR, test SRAM ou trampoline, successivement | `0x00028000` | Code avant `0x0003b000` |
| Pile SRAM du test et du trampoline | `0x0003c000` | Descendante |
| Résultat SRAM du test / jalon du trampoline | `0x0003d000` | 28 octets pour le test |
| Zone de travail FEL annoncée par le SoC | `0x00040400` | Ne pas recouvrir |
| Noyau décompressé | `0x40008000` | Vérification de taille avant le zImage |
| zImage | `0x42000000` | Avant `0x43000000` |
| DTB | `0x43000000` | 1 Mio maximum |
| Initramfs externe | `0x44000000` | Avant `0x47f00000` |
| Marqueur de validation mémoire | `0x47fff000` | 32 octets |

Le nouveau gadget composite utilise `1d6b:0104` et doit offrir à la fois un nouveau `/dev/cu.usbmodem*` et une interface Ethernet CDC-NCM sur macOS. La disparition de `1f3a:efe8` seule n’est pas un succès. Il faut vérifier la console, la configuration DHCP du Mac et une connexion SSH réelle. La console reste utile si le réseau ne démarre pas.

Pour vérifier DHCP, le ping, SSH, `lo`, `usb0` et les deux services, trouver le nom `enX` de l’interface NCM dans les réglages Réseau de macOS, puis :

```sh
sh stage1/tools/network-check.sh enX
```

Si macOS n’obtient pas de bail, configurer temporairement l’interface NCM en `10.77.0.2/24`, vérifier `ping 10.77.0.1`, puis exécuter :

```sh
ssh -i stage1/out/ssh/client_ed25519 -o IdentitiesOnly=yes root@10.77.0.1
```

## Vérifications déjà faites et limites

- Série V853 v2 : les fichiers modifiés par le rebasage ont été comparés octet par octet après application sur une extraction propre de Linux 7.2.7. La compilation `zImage` et DTB réussit sans avertissement de compilation ; le script `build-linux.sh` complet a été relancé avec cette version.
- Sur le dongle, après validation intégrale des 128 Mio, le noyau v2 a démarré depuis FEL avec un DTB de 11 592 octets. La console ACM a répondu à une commande Linux ; le Mac a reçu une adresse DHCP sur `en22`, le ping a répondu 2/2 et la vérification SSH de `lo`, `usb0`, `udhcpd` et `dropbear` a affiché `NETWORK_PROOF_OK`. Le second essai, avec les images du script final, a également réussi. Les preuves sont dans `logs/kernel-7.2.7-patchew-v2-usb-shell.log`, `logs/kernel-7.2.7-patchew-v2-network.log` et `logs/kernel-7.2.7-patchew-v2-remote.log`. Les SHA-256 des dernières images chargées sont `ff1c4ce92710f4ea766ce9085022b455d76ae080e9ba6443397f0af498dccedb` (zImage) et `2aa69346145075a87bf59616f10d3f8ef2b7930b57551b0b844695d92b8ef117` (DTB). Une recompilation ultérieure peut modifier ces sommes à cause des horodatages du build.
- Le schéma Device Tree complet n’a pas été contrôlé par `dtbs_check` (outil `dt-schema` absent du conteneur). Le test matériel couvre le chemin RAM, USB et réseau, pas tous les périphériques de la DTSI v2. Le message `sunxi-sram ... error -95` persiste ; il n’a pas empêché ces fonctions.
- Les portages 7.2.7 compilent avec CCU V853, pinctrl, PHY USB, MUSB Sunxi, gadget composite ACM/NCM, console série gadget et timer ARM. Le composite a été vérifié sur le dongle pour les deux versions.
- BusyBox est un exécutable ARM statique sans segment INTERP.
- L’archive initramfs contient `/init` exécutable, les liens BusyBox nécessaires, `/dev/console` (5,1) et `/dev/null` (1,3).
- Le pilote DDR C fait 8 616 octets ; les autres programmes SRAM restent dans leurs régions réservées.
- Les adresses USB/reset proviennent des pilotes et du patch V853. La transition FEL → gadget est validée sur le dongle ; le watchdog est armé pendant le lancement et `/init` l’arrête une fois le gadget USB configuré par l’hôte.
- Le code Linux conserve les horloges non utilisées (`clk_ignore_unused`). Le timer ARM est validé à 24 MHz. La DDR utilise les paramètres 936 MHz du firmware ; les autres périphériques ne sont pas validés par cet essai.
- Le dump complet et le boot0 ne sont jamais exécutés tels quels : le chemin actuel utilise le pilote DDR C d’awboot, avec les paramètres du boot0.

## Résultat matériel initial du 25 septembre 2026 (`g_serial`)

- DDR awboot V0.24 : 128 Mio, trois régions de 4 Kio vérifiées et relues sans alias.
- Test SRAM : deux passes adresse XOR masque sur `0x40000000..0x47ffffff`, PASS, phase 4, cache de données/MMU désactivés. Le marqueur de session est relu avant lancement.
- Noyau : `Linux (none) 6.13.0-rc1-v851s-ram-stage1`, ARMv7 Cortex-A7, timer physique 24 MHz.
- `/init` démarre vers 0,69 seconde dans le journal noyau ; le gadget série est prêt vers 0,65 seconde.
- Mémoire Linux : `MemTotal: 124412 kB`, sur 128 Mio physiques, après réservations noyau et 1 Mio de ramoops.
- Shell : BusyBox ash répond aux commandes via `/dev/cu.usbmodem1101`. Le marqueur `SHELL_PROOF_b3aa1217bdb3a052` est une sortie de commande et n’apparaît pas littéralement dans l’entrée envoyée.
- Preuves : `logs/stage1-validation.json`, `logs/ram-validated.json`, `logs/last-boot-images.json`, `logs/usb-shell-6.13.log`.

## Résultat matériel réseau du 25 septembre 2026 (ACM + CDC-NCM)

- Le gadget `1d6b:0104` s’énumère sur macOS : console `/dev/cu.usbmodemV851S_RAM_0011` et interface CDC-NCM `en22`.
- `udhcpd` attribue `10.77.0.2/24` au Mac ; le dongle utilise `10.77.0.1/24` sur `usb0` et `127.0.0.1/8` sur `lo`.
- Deux pings sur deux répondent. Dropbear 2026.94 accepte la clé cliente générée et exécute une commande SSH distante (`NETWORK_PROOF_OK`). Les processus `udhcpd` et `dropbear` sont présents.
- Preuves : `logs/network-validation.json`, `logs/network-usb-shell.log`, `logs/network-check.log`, `logs/network-remote-state.log`.

## Résultat matériel Linux 7.2.7 initial du 25 septembre 2026

- Le noyau annonce `7.2.7-v851s-ram-stage1` sur la console ACM et via SSH. Le test complet des 128 Mio a de nouveau réussi avant ce démarrage.
- Le gadget composite `1d6b:0104` expose la console `/dev/cu.usbmodemV851S_RAM_0011` et CDC-NCM `en22`. Le Mac reçoit `10.77.0.2` par DHCP ; `usb0` vaut `10.77.0.1/24` et `lo` vaut `127.0.0.1/8`.
- Le ping répond 2/2, et une commande SSH vérifie les adresses IP ainsi que les processus `udhcpd` et `dropbear`.
- Preuves : `logs/kernel-7.2.7-validation.json`, `logs/usb-shell.log`, `logs/kernel-7.2.7-network.log`, `logs/kernel-7.2.7-remote.log`.
- `sunxi-sram` signale encore `-95` au démarrage. Cela n’empêche pas le stage1 USB/réseau ; les autres périphériques du SoC ne sont pas couverts par cet essai.

Le dongle est laissé sous Linux 7.2.7 en RAM. Pour ouvrir la console sur ce Mac :

```sh
screen /dev/cu.usbmodemV851S_RAM_0011 115200
```

Une coupure USB perd ce Linux en RAM et ramène en FEL, puisque boot0 est effacé. Pour reproduire, exécuter `ddr-awboot`, `test-ram`, puis `boot` dans cet ordre. Lancer `python3 stage1/tools/usb-shell-check.py` avant `boot` pour attendre un nouveau port ACM et capturer automatiquement la preuve du shell. Le nom du port peut changer.

Le test mémoire recharge le watchdog par Mio et l’arrête lui-même avant de rendre FEL. L’hôte attend jusqu’à 120 secondes la commande USB suivante. Le lancement Linux arme un watchdog de 16 secondes ; `/init` l’arrête après configuration du gadget USB par l’hôte. Cette récupération requiert boot0 effacé. Ramoops a conservé les journaux après plusieurs resets watchdog pendant le débogage du gadget ; sa tenue après coupure électrique n’a pas été vérifiée.

Ce résultat valide le démarrage Linux en RAM, la console USB et le réseau USB avec DHCP et SSH. Wi-Fi, vidéo, audio et les fonctions applicatives du dongle n’ont pas été testés. MTD/SPI/MMC sont désactivés ; aucune écriture flash n’a été faite pendant ces essais RAM.
