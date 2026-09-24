# Historique des essais FES du 24 septembre 2026

Ces notes sont chronologiques et ne décrivent pas la procédure actuelle. Voir README.md.

## Essai du 24 septembre 2026 et prochaine reprise

À 23:08, FEL répondait à nouveau avec l’identifiant `0x00188600`. Les 19 584 octets de `ddr-stock.bin` ont été chargés en SRAM et relus à l’identique. Après son exécution, la commande `version` a expiré. Aucun test DRAM ni lancement Linux n’a donc suivi. Aucune écriture en flash n’a été faite.

Le désassemblage révèle une boucle infinie explicite à `0x2be98` lorsque l’initialisation retourne zéro, ainsi que des attentes matérielles sans limite ailleurs. Cela fournit des causes possibles, sans identifier le point de blocage de cet essai.

Un diagnostic **compilé mais non testé sur matériel** est prêt :

```sh
bash stage1/tools/build-sram.sh
python3 stage1/tools/prepare-ddr-diagnostic.py
# Après une coupure/reconnexion et la commande FEL du firmware d’origine :
python3 stage1/tools/ram-boot.py context
python3 stage1/tools/ram-boot.py diagnose-ddr
```

`context` relève SP, LR, CPSR, SCTLR, TTBR0 et VBAR dans `logs/fel-context.json`. Il refuse la suite en présence de MMU/cache de données actifs, d’un mode autre que SVC, ou d’une pile hors de la plage SRAM attendue. Il ne configure aucun périphérique.

`diagnose-ddr` répète cette sonde, charge une copie instrumentée du FES et utilise une pile SRAM à `0x3c000`. La sortie caractère est redirigée vers un tampon SRAM borné, l’initialisation UART est sautée et la boucle d’échec explicite revient par l’épilogue existant. Les octets originaux de chaque point de modification sont vérifiés avant de produire la copie ; `ddr-stock.bin` est conservé. Le wrapper à `0x2d100` restaure les registres préservés, la pile, CPSR et SCTLR au retour. Le logger est à `0x2d000`, son état à `0x3d000` et son tampon à `0x3d100` (3 584 octets maximum).

Si le code revient, le résultat et les messages sont enregistrés dans `logs/ddr-diagnostic-result.json` et `logs/ddr-diagnostic.log`. Seul un retour indiquant 128 Mio permet les vérifications DRAM partielles. Les attentes internes peuvent encore bloquer : cette instrumentation ne garantit pas un retour à FEL.

Lors de la reprise suivante, la sonde SRAM a fonctionné : SP `0x3f1fc`, LR ROM `0x9148`, CPSR `0x60000153` (SVC), SCTLR `0x00c50878` (MMU et cache de données désactivés). Le FES instrumenté et son wrapper ont été chargés et relus à l’identique, mais FEL n’a pas répondu après leur exécution. Aucun journal DDR n’a pu être récupéré, aucun accès de test DRAM ni lancement Linux n’a suivi.

La prochaine commande après retour physique en FEL est maintenant :

```sh
python3 stage1/tools/ram-boot.py preflight
```

Elle vérifie également que le compteur physique ARM avance, lit les registres PLL CPU/DDR/périphérique et CPU_AXI, puis exécute uniquement la bannière FES avant de revenir avec le résultat sentinelle 1. Cette variante saute l’initialisation UART et revient avant l’initialisation plateforme/horloges/DDR ; elle vérifie le chemin de capture des messages et le retour à FEL. Ses fichiers de sortie sont `logs/fel-clocks.json`, `logs/ddr-preflight.log` et `logs/ddr-preflight-result.json`.

Le désassemblage de la routine plateforme `0x28ed8` montre qu’elle appelle `0x28f5c`, qui reconfigure notamment la PLL CPU puis attend sans limite le bit de verrouillage. Dans cette séquence, elle ne positionne pas elle-même le bit d’activation 31 de la PLL CPU. Si la PLL est désactivée à l’entrée, cela fournit une autre hypothèse de blocage **à vérifier avec les registres**, avant toute conclusion sur la DDR. Le précontrôle n’a pas encore été essayé sur matériel.

La reprise matérielle exige une nouvelle coupure/reconnexion puis la commande FEL du firmware d’origine. Sans UART, un échec USB peut demander cette intervention. Ne pas effacer le bootloader pour faciliter cette boucle.

### Précontrôle réussi et nouvel essai du 24 septembre

Le précontrôle est maintenant **validé sur matériel** : le compteur ARM avance (malgré CNTFRQ à zéro), la bannière `fes begin commit:2a3ec52022` est capturée en SRAM et FEL répond après le retour. Les registres lus sont PLL_CPU `0xfa001000`, PLL_DDR `0xf8002301`, PLL_PERIPH `0xf8216310`, CPU_AXI `0x03000301`. La PLL CPU est donc activée et verrouillée : l’hypothèse d’une PLL CPU désactivée à l’entrée est écartée.

À 23:31, la variante `ddr-inherited-clocks.bin`, qui saute l’ensemble de l’initialisation plateforme `0x28ed8` (horloges CPU/périphériques et configuration d’alimentation associée), bloque également le retour à FEL. Les paramètres DDR du boot0 sont inchangés. Ce résultat ne localise pas encore le blocage : aucun journal n’est récupérable tant que le FES ne rend pas la main. Aucun test DRAM ni lancement Linux n’a suivi.

Trois variantes supplémentaires sont compilées, **non encore testées sur matériel**, pour arrêter l’exécution progressivement avant la configuration du contrôleur :

```sh
# Après retour physique en FEL, commencer par la première seulement.
python3 stage1/tools/ram-boot.py ddr-stage-zq
python3 stage1/tools/ram-boot.py ddr-stage-identity
python3 stage1/tools/ram-boot.py ddr-stage-parameters
```

- `zq` revient après la séquence ZQ, avant la routine `0x2ba2c` de vérification d’identité.
- `identity` revient après cette vérification, avant la configuration de tension DRAM `0x2a11c`.
- `parameters` revient après la configuration de tension et les impressions de paramètres, avant `0x2b44c` qui initialise le contrôleur.

Chaque variante conserve les horloges CPU/périphériques, détourne un point vérifié vers `0x2d300`, rétablit la pile du wrapper, puis utilise son chemin de restauration du contexte FEL. Le résultat attendu est la sentinelle `0x53544f50` et non une taille mémoire. Le wrapper et le logger font désormais 792 octets. La capture de chaque étape est conservée dans un fichier distinct `logs/ddr-stage-*.log`. Un échec en amont du point d’arrêt peut toujours bloquer et nécessiter une coupure physique.
