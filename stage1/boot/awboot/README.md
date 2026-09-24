# Pilote DDR d’awboot en SRAM

`dram.c`, `dram.h`, `reg-dram.h` et `reg-ccu.h` proviennent de
https://github.com/szemzoa/awboot/tree/5380c00fc67c975433f25c57fb481aa2b91aebf8/arch/arm32/mach-v851s
(licence GPL-2.0+, notices conservées).

Adaptations locales : sept attentes de registres bornées à 100 ms, journal en
SRAM, temporisations sur le compteur physique ARM à 24 MHz, contexte FEL
préservé et paramètres issus du boot0 d’origine. La fréquence CPU n’est pas
modifiée. Le bit de test mémoire intégré est retiré de la copie des paramètres ;
le programme SRAM séparé vérifie ensuite les 128 Mio intégralement.

Construction : `bash stage1/tools/build-awboot-ddr.sh` depuis la racine.
Le binaire est lié à `0x28000`, fait 8 616 octets, et n’utilise aucune flash.
Le watchdog matériel est armé par l’hôte avant exécution.

Le 25 septembre 2026, le pilote a rapporté 128 Mio et les trois tests de 4 Kio
aux adresses `0x40010000`, `0x44010000`, `0x47ff0000` ont réussi, y compris les
relectures croisées. Le test complet a ensuite rendu `PASS`, phase 4.
Le délai de la commande USB suivante était trop court ; la preuve de rétention
après récupération a échoué. Aucun marqueur `ram-validated.json` n’a été créé
pour cette session. Le watchdog est désormais arrêté par le test avant son
retour à FEL, et l’hôte attend jusqu’à 120 secondes la commande suivante.

Après rebranchement, le test corrigé a validé les deux passes et son marqueur de session. Linux 6.13-rc1 puis le shell USB ont démarré avec succès ; voir `../../logs/stage1-validation.json`.
