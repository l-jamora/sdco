---
tags:
  - icom
  - raquel
Status:
  - Ongoing
---
# Continued Work 08.07.2026

- 






# Notes
- Proposal / paper title?

- PositionFrom / PositionTo explanation
	- DIN EN 13508-2: ![[Pasted image 20251108101034.png]]


- Individual Examples (Prefixed with 0_ so it jumps to the top of the list)
	- `0_PipeSection001` inspectedby
		- `0_InspectionReport_001` isParentOf
			- `0_ConditionReport_001_1`
			- ![[Pasted image 20251108095426.png]]
				- ISYBAU 2017 Example
					- No Date in example? Put in placeholder.
	- 0_Node001
		- 0_InspectionReport_002
			- 0_ConditionReport_002_1

- TBox vs. ABox? Verify if correct.
	- TBox is more object properties?
	- ABox more class assertions?

- AI Chatbot?
	- GraphDB
	- LangChain


---

# 0. Abstract


---

# 1. Introduction

- **Background and Motivation:**
	- What are the current challenges in managing and analyzing sewer condition data?
		- Large amounts of data consists within a sewage system.
		- Currently, sewer data information is exchanged in the XML format (M150-XML). 
		- Financial constraints and limited political support in the sewage sector frequently lead to reactive rather than proactive maintenance
			- adoption of predictive maintenance methods lies in managing and exchanging large amounts of data, modeling component relationships, and formalizing operational knowledge including physical asset details and real-time operational metrics. Traditional methods struggle to handle this diversity and volume efficiently.
	- Digital twins -- a very relevant topic and answer to the issue of converting reactive maintenance standards to more proactive maintenance standards, by predicting where maintenance has to be done, before the damage comes into fruition. 
		- Digital twins have become very relevant for research into infrastructure maintenance. Example: Research is being done on the digital twinning of road infrastructure with the same goal of using predictive analytics to prevent damage from even occurring in the future: Project is called SFB TRR 339 ([DFG - GEPRIS - TRR 339: Digitaler Zwilling Straße – Physikalisch-informatorische Abbildung des Systems „Straße der Zukunft“](https://gepris.dfg.de/gepris/projekt/453596084)) [Home - Future Road System](www.sfbtrr339.de/en/) (find a reference here)
		- To create digital twins, the data from the real world has to be modelled in a digital model somehow. So how is this data (or knowledge) going to be collected and represented? --> Ontologies serve as a method for knowledge representation. This enables not only the collection of data in a defined structure, but also to give meaning to the data involved, with the goal of 
		- To answer this goal, M150-Onto was developed as an ontological approach to this problem. 
			- However, M150-Onto lacked in the classification of damages.
	- Why is an ontology needed for the main goal of achieving digital twinning of sewage infrastructure?
		- When M150-Onto was developed, more focus was put on modelling the data described by the references tables found in DWA M150 (examples were the pipe materials, etc.). However, the inspection and condition report data, though reflected as data properties, were not linked nor defined with any classes. 
			- This was exacerbated by the fact that the testing data provided by Würselen did not include inspection and conditon report data.
		- The idea of SDCO is to complement and supplement M150-Onto by providing a semantic layer for damage classification according to the DIN EN 13508-2 standard. 

> [!tldr] Research Objectives: **not final**
> - Is there a gap in research for domain ontology in sewer damage classification?
> - How can DIN EN 13508-2, which currently exists as a paper- and XML-based classification system, be formalized into a domain ontology?
> - How does the proposed sewer damage classification ontology **improve** upon the original DIN EN 13508-2 classification system in terms of **data interoperability**, **query complexity**, or **inference capabilities**?

- This paper is structured as such:
	- This paper first describes the background and related work (where the classification system according to DIN EN 13508-2 is explained, as well as similar implementations to sewer damage classifications
	- Then introduce the sewer damage classification ontology (SDCO for short) and how it came to fruition using a 7-step ontology modelling process derived from the Methontology paper.
	- Afterwards, we will then discuss the use cases and potential linking with other ontologies, as well as the use cases, benefits, limitations and outlook for future research.



---

# 2. Background / Related Work

- Kasytwin

-  M150-Onto

- **DWA M150: Data Exchange Format**
	- 

- **DIN EN 13508-2: Visual Inspection Coding System**
	- The DIN EN 13508-2 standard defined the process and coding system for visual inspections of drain and sewer systems
	- Information can be exported as an XML or in the character separated format.
		- The XML format described in the standard closely mirrors the inspection and condition data structure of DWA M150.
			- DWA M150: Inspection Report (Report about what is being inspected) is the parent of several condition reports (Report that describes each observation)
			- DIN: ZB describes the inspection header information (in other words the drain or sewer that is being inspected) and ZB is the parent of ZC, which describes the individual observations of the inspection.
			- Insert figure here that describes the structure of the XML according to DIN: ![[Pasted image 20251119091308.png]]
	- A visual inspection is conducted with photographic recordings (CCTV) by examiners.
	- A total of 80 codes describe damages or observations/inventory of a pipeline or a manhole/inspection chamber (node).




- Scopus AI: Prompt: "Look for ontological implementations for damage classifications according to DIN EN 13508-2"
	- Follow-Up Prompt: "DIN 13508-2 is about damage classifications for pipes."
	- [Hamdan A - (PDF) An ontological model for the representation of damage to constructions](https://www.researchgate.net/publication/334326699_An_ontological_model_for_the_representation_of_damage_to_constructions)
	- [Anderlik S - A proposal for ontology-based integration of heterogeneous decision support systems for structural health monitoring \| Proceedings of the 12th International Conference on Information Integration and Web-based Applications & Services](https://dl.acm.org/doi/10.1145/1967486.1967515)
	- [Hamdan A - (PDF) Areas of Interest - Semantic description of component locations for damage assessment](https://www.researchgate.net/publication/353221182_Areas_of_Interest_-_Semantic_description_of_component_locations_for_damage_assessment)
	- [Hamdan A - Modular concatenation of reference damage patterns](https://www.scopus.com/pages/publications/85079323051)
	- [Maiwald H - edac.biz/fileadmin/Dokumente/06\_Publikationen/Bautechnik\_1018\_Maiwald\_Schwarz.pdf](https://edac.biz/fileadmin/Dokumente/06_Publikationen/Bautechnik_1018_Maiwald_Schwarz.pdf)
- Ontological Approaches (similar)
	- Scopus AI: Prompt: "Conduct a comprehensive review of the development and application of ontological implementations for damage classification according to DIN EN 13508-2. The search should identify existing ontologies, knowledge-based systems, and formal models used to classify damage in sewer systems, including their methodologies, benefits, and challenges."
	- [Consistent Classification System for Sewer Pipe Deterioration and Asset Management \| Journal of Water Resources Planning and Management \| Vol 148, No 5](https://ascelibrary.org/doi/10.1061/%28ASCE%29WR.1943-5452.0001545)
		- No access, also doesn't seem like its an ontological approach. But could be used for referencing. Email sent for a copy.
		- Copy: [bipnz.org.nz/wp-content/uploads/2022/09/Tizmaghz-2022-JWRPM-Consistent-Classification-System-for-Sewer-Pipe-Deterioration-and-Asset-Management-1.pdf](https://bipnz.org.nz/wp-content/uploads/2022/09/Tizmaghz-2022-JWRPM-Consistent-Classification-System-for-Sewer-Pipe-Deterioration-and-Asset-Management-1.pdf)
	- [A Proposal for Ontology-based Integration of Heterogeneous Decision Support Systems for Structural Health Monitoring](https://dl.acm.org/doi/pdf/10.1145/1967486.1967515)
		- "Approach to ontology-based integration of Decision Support Systems for Structural Health Monitoring, specifically the implementation of a damage detection strategy for identifying and localizing damages to (civil) infrastructure (e.g., bridges, piping systems or wind turbines)."
- Non-Ontological Approaches
	- Machine Learning Approaches
		- [Application of regression methods for classification of sewers’ damages \| Applied Water Science](https://link.springer.com/article/10.1007/s13201-021-01488-0?getft_integrator=scopus)
			- The main aim of the paper was to check if prediction methodology could be useful for classification of different kinds of sewers damages. The obtained results pointed out that proposed classification methods are not appropriable in quality analysis of registered damages of sewers. Moreover, it is recommended for water and sewerage companies to register types of failures using unified notation which make easier preliminary classification before applying modelling approach. The calculations were performed in Statistica 13.1 software.
	- Computer Vision and Deep Learning Approaches

- [(PDF) An ontology of condition assessment technologies for sewer networks Jehan Zeb](https://www.researchgate.net/publication/340129929_An_ontology_of_condition_assessment_technologies_for_sewer_networks_Jehan_Zeb)
	- Cats_Onto introduces the Subclass: Defects (Under Criteria --> Detectability --> Defects). It has the following classes:
		- Break
		- Corrosion
		- Crack
		- Deformation
		- Exfilteration
		- Fracture
		- Hole
		- Joint_Leakage
		- Leakage
		- Lining_Failure
		- Obstruction
		- Pulled_Joint
		- WRE_Base_Line
		- WRE_Real_Time
	- Zeb developed their own class for defects/damages, likewise indicating that a domain ontology for sewer damage classification is not available.
		- Some of these classes introduced by Zeb can represent some damage codes found in DIN EN 13508-2. However, not every 
	
- [ceur-ws.org/Vol-2389/05paper.pdf](https://ceur-ws.org/Vol-2389/05paper.pdf)
	- Damage Topology Ontology = DOT
	- Very relevant paper that came closest to the goal of this paper. This ontology will be further inspected after the chapter describing SDCO, with a more thorough analysis and a attempt to link.
		- Benefit: This would be the first ontology to link with W3C Linked Building Data Community [W3C Linked Building Data Community Group · GitHub](https://github.com/w3c-lbd-cg) ; [Linked Building Data Community Group](https://www.w3.org/community/lbd/)
	- The Damage Topology Ontology (DOT) allows the definition of damage representations and their relations with other damages and affected construction components. The ontology supports a generic damage modeling approach and therefore could be applied for any type of degradation as well as for any construction type (e.g. buildings or bridges). Damage representations can be modeled either as damaged areas ([dot:DamageArea](https://alhakam.github.io/dot/#DamageArea)) or elementary damage elements ([dot:DamageElement](https://alhakam.github.io/dot/#DamageElement)). Thereby, instances of [dot:DamageElement](https://alhakam.github.io/dot/#DamageElement) should be aggregated in a [dot:DamageArea](https://alhakam.github.io/dot/#DamageArea), however significant damages e.g. large cracks could be modelled as [dot:DamageElement](https://alhakam.github.io/dot/#DamageElement) without [dot:DamageArea](https://alhakam.github.io/dot/#DamageArea).

> [!important] Which leads to the conclusion: 
> **Though damage classification is a common subject in the goal of digital twinning, there is a clear gap in research for ontological implementations specifically for the domain of sewer damage classifications.** 

---

# 3. SDCO

- This section is going to be about the sewer damage classification ontology (SDCO): how it was developed, how it was tested, etc. etc.
- For development, a 7 step approach same as m150-onto, derived from Cats_onto, and modified originally from the Methontology ([METHONTOLOGY\_.pdf](https://oa.upm.es/5484/1/METHONTOLOGY_.pdf)), process. Methontology is not a standardized method for creating ontologies, however it is widely used in the field of ontology creation.

## Step 1: Scope Definition
copied from M150-Onto. **Edit** for more towards SDCO.
- The primary purpose is to support comprehensive asset and data management of sewage infrastructure. It is an ontological model of the DIN EN 13508-2 visual inspection coding system / damage classification system. Sewage infrastructure data, and inspection data specifically, is inherently complex, encompassing a wide variety and volume of inputs, records, measurements, and information. By formalizing this domain knowledge within an ontology, we enable more sophisticated data integration, analysis, and reasoning capabilities.

- The primary intended use of SDCO is to facilitate knowledge queries for various usages that require information about a sewage system, e.g. predictive maintenance decision support. For example, if an engineer knows that pipes with certain materials demonstrate particular damage patterns after a specific number of years, \textit{how can we efficiently identify all pipes with these characteristics within a sewage system comprising thousands of diverse components?} M150-Onto enables automated reasoning and enhanced querying for such operational decisions.

- The primary target users of M150-Onto are professionals responsible for the maintenance of sewage systems and those planning system expansions. This includes municipal engineers, maintenance crews, and urban planning professionals who need to navigate complex sewage infrastructure data. In essence, M150-Onto serves any user who requires structured access to the complex and extensive knowledge domain represented by a sewage system.

## Step 2: Metamodel Development

- The main source of information is from the DIN EN 13508-2 standard. This was exclusively used for modelling, due to its extensive use in various countries. M150-Onto, as well as DWA-M150, and its inspection and condition report structures are explicitly modelled for ease of incorporation of damage reports following the DIN EN 13508-2 structure.
	- Compilation of all damage codes described in DIN EN 13508-2 (total of 80 codes describing damages, conditions, inventory codes, etc.)
- The metamodel was developed with the help of a spreadsheet. This is where the main knowledge information about the DIN standard was collected, and served as the basis for ontology development. 
- First collected all the codes found in the standard into a worksheet.
- Additionally investigated the XML format, to be used for the implementation part of this. The xml format could be used to automate conversion from DIN XML to the ontology using owlready2.


## Step 3: Taxonomy Definition

### Taxonomy of Component
- Directly imported from M150-Onto. This describes the main assets of a sewage system.
	- The Class:Node describes the points/structures where PipeSections connect. These could be inspection chambers, manholes, etc.
	- The class:PipeSection describes the pipes that connect these nodes.
### Taxonomy of Report
- Likewise directly imported from M150-Onto. This describes the inspection and condition reports as defined by DWA-M 150.
	- Inspection reports are reports that collect general information about an inspection: Information such as when and where the inspection took place, who is the inspector, what standard was used (like DIN EN 13508-2), etc.
		- An inspection report can contain several condition reports.
	- Condition reports describe individual observations, such as damages, inventory status', etc. So there would be one condition report for a deformation observed by the inspector, and a separate that e.g. describes vermin spotted within the pipes.
### Taxonomy of Observation 
- The subclass **Damage** was supposed to be one of the main taxonomies (so originally, there was a Taxonomy of Damage), however **Observation** was more fitting after further investigation.
	- This is due to the fact that although the majority of codes described some kind of damage, some codes also described a simple observation, where it could not be classified as a damage.
		- Examples: Alongside damage codes such as fissures or deformation, other codes also describe the inventory of pipes.
		- Several damage codes also describe the orientation of the damage. Therefore, the subclass Orientation was also created as a subclass of Observation.
		- Some damage codes also describe the cause of the damage (these are codes describing surface damages BAF / DAF) 
		- Therefore, the superclass Observation was created, with Damage assigned as a subclass of Observation
	- Originally, **Damage** was planned to be separated into subcategories mirroring chapters of the DIN EN 13508-2 standard (example: PipeFabricDamage and NodeFabricDamage), however it was soon realized that the majority of these codes overlapped and described similar damages. Therefore, codes for pipe and node damages that both described a similar damage (such as deformation or fissure) were assigned the same class, but this still leaves the need for differentiation of the characteristic damage (example: how do we differentiate a pipeline fabric vertical deformation damage (BAA with characterisation A) / a pipeline horizontal deformation damage (BAA with charaterisation B) /  a manhole bzw. node fabric localised deformation (DAA with characterisation B))
		- The solution for this was to introduce a new sub-object properties 'hasNodeDamage' and 'hasPipeDamage', with its super-object property being hasDamage. This first differentiates the damage to either a node or a pipeline. Moreover, it also successfully describes the general term hasDamage, due to structuring as sub-object properties. Later on in development, more object properties such as hasPipeOperationDamage have been introduced to further substantiate between types
	- **Update to the Damage subclass 3.12.2025:** Originally called **Damage**, this was now renamed to **Defect** due to some operation codes (such as BBA (observed roots of trees or other plants growing into the pipeline)) is more accurately described as an operational defect rather than damage. Defect is now a catch-all phrase for this.
		- Later on, the subclasses **StructuralDefect** and **OperationalDefect** were introduced to differentiate between structural and operational defects. 
- This taxonomy also contains the subclass "**Inventory**" -- this class consists of subclasses that describe various inventory features of a pipe/node, such as the pipe connection type (BCA), node types (codes BCD, BCE describe the node type of which the pipe is connected to (differentiated by start and finish node types), point repairs done (Code BCB) and the curvature of the sewer (code BCC).
- This taxonomy also contains the subclass "**OtherObservation**" -- this class represents the codes categorized as "Other Codes" in the DIN standard. This consists of photographs (code BDA) and remarks (code BDB) regarding an object,  
	- These classes are linked to individuals through the **hasPipeFeature** object property.
	- The object property **hasTerminationReason** was also introduced for code BDC (Inspection terminated) to link the reasons of the termination of inspections.
	- The object property **hasWater** was also introduced for codes BDD (describes the water level above the invert of a drain/sewer) and BDE (describes the water flowing from an incoming pipe)
		- The subclass **Wastewater** describes the different kinds of wastewater that can be observed and categorized for codes BDD and BDE.
	- The object property **hasObstructionReason** was also introduced for the code BDG (describes that the view of the pipeline is obstructed). 
- This taxonomy also contains the subclass "**Cause**" -- as briefly mentioned before -- to describe the cause of the damage. According to the DIN EN 13508-2 standard, describing the cause of the damage is exclusive to the surface damage codes BAF / DAF (pipe and node damage respectively). 
	- The **Cause** subclass has also now been expanded to further describe the codes BDC / DDC (Inspection Termination), which describes reasons for inspection termination reasons.
	- This subclass has also now been expanded to describe the obstruction reasons for BDG (Loss of vision: view of the pipeline is obstructed) and linked through the object property **hasObstructionReason**.
- This taxonomy also contains the subclass "**Orientation**" -- as briefly mentioned before -- to describe the orientation of a damage, which is described as one of the characterization codes in DIN EN 13508-2.
	- For example: The damage code BAA (which describes a pipe fabric damage -> deformation" has two characterization codes that describes the orientation of the deformation: A = vertical, which means the height of the pipe has been reduced. B = horizontal, the width of the pipe has been reduced.
	- The directions and orientation "Left, Right, Up and Down" have also been added to the Orientation subclass to describe the inventory code BCC (Sewer Curvature)
- This taxonomy also contains the subclass "**Location**" -- to describe the location of vermin (damage code BBH, second characterization code). At the moment, it is only exclusively used for the damage code representing Vermin, however this taxonomy shows a lot of promise for further other damage codes.  


### Taxonomy of Rehabilitation

- **Kurzliner**: [Kurzliner - Sanierung nicht begehbarer Kanäle - YouTube](https://www.youtube.com/watch?v=_IsuR1Puk5U)
	- Glasfasermatte mit speziellen Harz (Epoxid/Silikatharz) wird um ein aufblasbaren Gummizylinder gewickelt.
	- Gummizylinder wird zum Ort des Schadens innerhalb des Röhres geschoben.
	- Gummizylinder wird aufgeblasen, sodass die Matte mit Harz gegen die Innenwand des Rohre presst. 
		- Harz dringt dabei in Risse ein.
	- Nach 60-90 min ausgehärtet, Verpacker wird entlüftet und herausgezogen
	- Resultat: dichte Innenschale

- **Schlauchliner**
	- Ein **Schlauchliner** (oft auch einfach Inliner genannt) ist – im Gegensatz zum punktuellen Kurzliner – ein Verfahren zur vollständigen Sanierung einer Abwasserleitung auf ihrer gesamten Länge.
	- "Rohr im Rohr"




### Taxonomy of Cost






### Taxonomy of Characterization 

- Lastly, the Taxonomy of Characterization was created to map the characterization and condition codes from DIN to its respective damage and characterization options. This decision occurred during the prototypical development of this ontology. More details in next step.
- Originally, it was assumed that the taxonomy of observation would be sufficient. So example the Class:CrackFissure would be set equivalent to:
- `(hasConditionCode value "BAB" and hasCharacterization1 value "B") or (hasConditionCode value "DAB" and hasCharacterization1 value "B")`  to take both node-specific and pipe section-specific fissures into account. However, this would have defined every condition report with these data properties as a type of CrackFissure, which is logically not what we are going for. We want to describe them solely as object properties (so goal is only to tet the inferred object property hasDamage Fissure, in the example of Class:CrackFissure). 
	- Therefore, the intermediate classes for mapping contains all the codes found in the DIN standard.
- Maybe change this taxonomy name to `DIN EN 13508-2`????

> [!todo] TODO: Full Graph similar to this
> ![[Pasted image 20250910113944.png]]
> 
## Step 4: Ontology Coding

- The ontology was prototypically implemented into Protege. Before scaling with the entire damage codes, the goal of the prototype is to see which approach would be the most efficient for scaling. 
	- For this prototype, we will be testing the damage code BAB, which represents Fissure damage according to DIN. This fissure damage is categorized into 3 different characterization code 1 options which represent the nature of the fissure, as well as different characterization 2 options that represent the orientation of the damage. Several approaches were considered:
		  1. **SWRL+OWL approach**: Mapping with SWRL and intermediary mapping individuals, with the introduction of DamageMapping Class
		  2. **Pure SWRL approach**: Each characterization code and its various characterization combinations would have received their own SWRL rule.
		  3. **Pure OWL approach**: Inferences through OWL Equivalencies without any SWRL usage. 
	- So with this prototype, we are trying to answer the question: How can we map the condition reports to its damage most efficiently and apply this approach for when we scale it with the rest of the damage codes? The original goal: Pure OWL2 implementation without SWRL. However, this would mean creating hundreds of new classes with equivalent classes for each ConditionCode+Characterization combinations for mapping.
		- Therefore, it was then decided to use SWRL for the if-mapping, introducing an intermediate DamageMapping class layer.
		- However, this proved to be laborious and time-consuming, due to the fact that individuals had to be inputted for each characterization 1/2 combination, AS WELL as individuals for mapping. (Doppelt-gemoppelt)
- Originally, each code in the super class characterization (example BAB_A) was given the equivalent to axiom to its characterization code (BAB_A = BAB and (hasCharacterization1 value "C"). This however made the illogical -- though consistent -- inference, that it is therefore equivalent to any other code that shared the 
	- Instead, the following final version was developed: In the taxonomy of characterization, each damage code according to DIN EN 13508-2 is represented as a class with its respective code as its superclass. The subclasses of a damage type represent the various characterization options for the damage code (CharacterizationX (1 or 2) following the template DamageCodeX_CharacterizationCode, so example BAB2_A means BAB: Pipe-specific Fissure Damage, 2: Characterization2, A: Longitudinal orientation for the fissure damage)

- Once this finalized version for coding was realized, Cellfie (a built-in protege plugin) was used to mass import these damages as classes with its corresponding punned individual (Punning: Term in ontology coding, where classes and individuals share the same IRI). Punning is required due to the TBox approach of assigning damage characteristics to condition reports.
	- This was later revisited: the mass-imported `owl:hasValue` restrictions produced by Cellfie were converted to `owl:someValuesFrom`, and the punned individuals were removed, since `someValuesFrom` achieves the same TBox-level characterization without punning. See the Limitations section and [`Punning_Refactor_Plan.md`](Punning_Refactor_Plan.md).

- BCE/BCD are inventory codes that describe the node types it is connected to / from. For these codes, the object properties hasStartNodeType and hasFinalNodeType have been introduced.

- BCC is an inventory code that describes the curvature of a sewer. The super object property hasCurvatureDirection and its sub-object properties hasHorizontalCurvatureDirection and hasVerticalCurvatureDirection have been introduced to describe this inventory code further.

- BBH and DBH are defect codes that describe the presence and location of vermin. To describe the location, the object property hasLocation was made. This object property, even though in the current state of the ontology lacking, has potential to be used to further describe other damage codes as well.
	- Example?

## Step 5: Ontology Axiomatization

- The object property hasDamageOrientation was given the following
	- Functional	✓ Check	A single instance of damage can only have one orientation (e.g., Damage A can't have both Circumferential and Longitudinal orientation). This enforces the "one orientation" constraint.
	- Asymmetric	✓ Check	If Damage A hasDamageOrientation Orientation B, Orientation B cannot hasDamageOrientation Damage A. The relationship only goes one way.
	- Irreflexive	✓ Check	Damage A cannot hasDamageOrientation Damage A. A thing cannot relate to itself in this manner.

## Step 6: Ontology Evaluation

- From Methontology cited: [REV\_JCR\_07\_C.pdf](https://oa.upm.es/72438/1/REV_JCR_07_C.pdf)
- "evaluation," "verification/' "validation/' and "assessment."



## Step 7: Ontology Documentation






## Linking with other ontologies (section title WIP)

- M150-Onto
- DOT
- [ceur-ws.org/Vol-2389/05paper.pdf](https://ceur-ws.org/Vol-2389/05paper.pdf)
	- Damage Topology Ontology = DOT
	- Very relevant paper that came closest to the goal of this paper. This ontology will be further inspected after the chapter describing SDCO, with a more thorough analysis and a attempt to link.
		- Benefit: This would be the first ontology to link with W3C Linked Building Data Community [W3C Linked Building Data Community Group · GitHub](https://github.com/w3c-lbd-cg) ; [Linked Building Data Community Group](https://www.w3.org/community/lbd/)
	- The Damage Topology Ontology (DOT) allows the definition of damage representations and their relations with other damages and affected construction components. The ontology supports a generic damage modeling approach and therefore could be applied for any type of degradation as well as for any construction type (e.g. buildings or bridges). Damage representations can be modeled either as damaged areas ([dot:DamageArea](https://alhakam.github.io/dot/#DamageArea)) or elementary damage elements ([dot:DamageElement](https://alhakam.github.io/dot/#DamageElement)). Thereby, instances of [dot:DamageElement](https://alhakam.github.io/dot/#DamageElement) should be aggregated in a [dot:DamageArea](https://alhakam.github.io/dot/#DamageArea), however significant damages e.g. large cracks could be modelled as [dot:DamageElement](https://alhakam.github.io/dot/#DamageElement) without [dot:DamageArea](https://alhakam.github.io/dot/#DamageArea).
	- The **Taxonomy of Damage is imported from the DOT ontology** (Damage topology ontology) that describes







---

# Discussion

## DL Query

### Knowledge / Information Questions
Q1: Retrieve all PipeSections with any kind of Fissure damage. // Look for a pipe section, that is reported to have the any kind of fissure damage.
> PipeSection and (inspectedIn some (Inspection and (isParentOf some (Condition and (hasDamage value Fissure)))))

Q2: Look for pipe sections, that specifically has the pipe damage crack fissure according to DIN.
> PipeSection and (inspectedIn some (Inspection and (isParentOf some (Condition and (hasPipeDamage value CrackFissure)))))

Q3: Look for a node, that has this damage with this orientation. (???)

Q4: Find all conditions report that indicate a FractureFissure.

Q5: Identify inspection reports with multiple damage types.



### Competency Questions
Q1: According to DIN EN 13508-2, what kinds of fissure damages are there?

Q2: According to DIN EN 13508-2, what kind of orientation can a pipe fissure damage be?



## SPARQL
(pronounced SPARKLE)

- Which pipe section has a crack fissure reported in its reports? What station?
```
PREFIX sdco: <http://www.semanticweb.org/jluis/ontologies/sdco#>
PREFIX m150-onto: <https://l-jamora.github.io/m150-onto#>

SELECT ?pipeSection ?station
WHERE {
  ?inspection a m150-onto:Inspection ;
              m150-onto:isParentOf ?condition .

  ?condition a m150-onto:Condition ;
             m150-onto:hasConditionCode ?code ;
             m150-onto:hasPipeSectionConditionStation ?station .

  FILTER(?code = "BAB")

  ?pipeSection a m150-onto:PipeSection ;
               m150-onto:inspectedIn ?inspection .
}

```



## SHACL Rule Checking
- While OWL adds meaning and reasoning to data compared to XML, SHACL can validate the data.

- Check if all conditions reports have a condition code. If not, then mark as a violation.
```
@prefix rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix sh:    <http://www.w3.org/ns/shacl#> .
@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl:   <http://www.w3.org/2002/07/owl#> .

@prefix sdco: <http://www.semanticweb.org/jluis/ontologies/sdco#>
@prefix m150-onto: <https://l-jamora.github.io/m150-onto#>


# Define a NodeShape targeting instances of m150-onto:Condition
m150-onto:ConditionShape
    a sh:NodeShape ;
    sh:targetClass m150-onto:Condition ;     # Applies to all instances of this class
    sh:property [
        sh:path m150-onto:hasConditionCode ; # Property to check
        sh:minCount 1 ;                       # At least one must exist
        sh:maxCount 1 ;                       # At most one (optional, but common for codes)
        sh:message "An instance of m150-onto:Condition must have exactly one hasConditionCode." ;
    ] .

```


- Check if a mandatory row for information for an inputted condition report is present or not.

- More complex SHACL examples:
	- Check if a given damage code has a valid characterization or not. For example, if a condition report reports a damage orientation, even though it shouldnt (e.g. Vermin), then return a violation.



## Benefits

- This work on SDCO contributes to the KaSyTwin project's objectives by providing the semantic foundation necessary for structuring and reasoning about sewer condition data within digital twin environments. 
	- (To answer: KaSyTwin aims to develop a methodology for the semi-automated development and utilization of digital twins of sewer systems using advanced multi-sensor robotic platforms equipped with laser scanners and cameras, combined with artificial intelligence for real-time damage detection and resilience forecasting \cite{kasytwin}.)

- Expands the goal from m150-onto of a full digital model of sewage infrastructure with damage classifications.
	- Although it was possible beforehand to input inspection/condition report data into M150-Onto, this was only inputted data. Now we are giving meaning to this part, which was not done with the current version of M150-Onto yet.
	- Integration with existing standards (DIN, DWA)
	- Unification of data from KIS/GIS/ and now with this the inspection report and condition reports given by inspectors / CCTV / robots as well.
		- This design allows SDCO to serve as the **semantic bridge** between video inspections, GIS-based networks, and future digital twins.

- Possible to link with machine learning for predictive analytics (Prediction of failure risks, optimizing maintenance schedules, etc.)
	- Prototype tested using GraphDB's experimental LLM feature. It can answer basic competency questions, however, it struggles when it has to do more complex SPARQL query work. More research into this will have to be done as the LLM feature also has other input methods available.
	- Perhaps in the future, AI models could be trained to predict future defects using different parameters, such as soil type, age, pipe material, etc.

- Independent from Geometry (supports Pre-BIM or non-3D data)
	- DOT deliberately separates _topological_ from _geometrical_ damage representations — allowing damage data to be modeled **even before** a 3D BIM model exists.

- 📹 **3. Automated Condition Assessment From CCTV**
	Future pipelines will be inspected using:
	
	- AI-based defect recognition (YOLO, CNN)
		
	- CCTV robots
		
	- Laser scanners
		    

	SDCO could become the **target schema** for auto-detected defects.
	
	If an AI detects a fissure:
	```
	sdco:CrackFissure
	m150-onto:hasConditionCode "BAB"
	m150-onto:hasPipeSectionConditionStation 31.4
	m150-onto:hasQuantification1 2.0 (length)
	```
	
	The robot inspection system can automatically generate new RDF triples → updating the digital twin immediately.
	
	### Example workflow (Insert figure here about:
	
	1. Robot scans pipe
	    
	2. AI identifies damage
	    
	3. REST API converts defects → ontology statements
	    
	4. Digital twin updates instantly
	    
	5. Operators receive notifications)


## Limitations

- Time-consuming and laborious process for translating the XML data into the ontology.
	- This can be remedied by implementing a python script, similarly to the M150-Onto approach using owl2ready.

- Some Damages were difficult to differentiate when being represented in the ontology.
	- For example, some characterizations from differing damage codes have identical descriptions. Characterization code C for BAC (Break/Collapse for Pipes) describes a collapse: complete loss of structural integrity.
		- Similarly, the  characterization code D for the damage code BAD (Defective brickwork or masonry) also describes a collapse: complese loss of structural integrity.
			- To differentiate these two types of damages and its subcharacteristics, clear wording for each type of damage has to be maintained. Class:CollapsedBrickworkOrMasonry vs. Class:CollapsedBreakOrCollapse.
	- Another Example is the characterization 'Missing Wall' that is a characterization for a break/collapse and for surface damage as well. The ontology would have been inconsistent if these classes were named identically, due to the disjointedness of the damage codes.
		- As a solution to differentiate between these two, further details into the names were applied (Class:MissingWallSurface vs. Class:MissingWallBreakOrCollapse)
	- The drawback from this approach is seemingly redundant naming conventions, as exhibited by the classes CollapsedBreakOrCollapse or MissingWallBreakOrCollapse.
		- Though it would be preferred to unify these codes as one singular class, this would mean that a revision of the DIN EN 13508-2 document is needed to address these redundancies. Therefore, the redundant naming convention was ultimately used.

- ~~Punning was used! Even though stated to be not recommended when creating ontologies. (find a reference for this)~~ **Resolved** — see `dev-classes_approach`. Every `owl:hasValue :Term` restriction on the characteristic properties (`hasPipeFabricDamage`, `hasDamageOrientation`, `hasLocation`, etc.) was rewritten as `owl:someValuesFrom :Term`, and the ~204 punned `owl:NamedIndividual` declarations that existed only to satisfy `hasValue` were deleted. `someValuesFrom` takes a class expression directly, so no individual is needed, and subsumption (e.g. `CrackFissure ⊑ Fissure`) now flows through the reasoner automatically — confirmed with HermiT, which correctly reparents e.g. `DAB2_A` under `Defect` without any extra axioms. See [`Punning_Refactor_Plan.md`](Punning_Refactor_Plan.md) for the full rationale and process.
	- Two branches were created to resolve this: `dev-classes_approach` (map characteristics through classes + `someValuesFrom`, chosen) and `dev-instances_approach` (map characteristics through individuals only, no class hierarchy). The instances approach is kept on the remote as a documented alternative — it was considered because it avoids restating the taxonomy as classes at all, but it was passed over because it sacrifices the automatic subsumption reasoning (e.g. `CrackFissure ⊑ Fissure`) that the classes approach gets "for free" from the reasoner.

- No expert opinion yet. 


## Outlook

- This ontology can be used as a basis. Automated code checking compliance could be done with SWRL.
- From Taxonomy of Observation: NOT FLESHED OUT YET: This taxonomy also contains the subclass "Cause" -- as briefly mentioned before -- to describe the cause of the damage. According to the DIN EN 13508-2 standard, describing the cause of the damage is exclusive to the surface damage codes BAF / DAF (pipe and node damage respectively). However, despite the lack of usage in other damage codes, this could be seen as an opportunity for further expansion of this ontology in the future.
- SHACL Rule Checking




# Appendix

- Full list of damages

- ISYBAU Dataset