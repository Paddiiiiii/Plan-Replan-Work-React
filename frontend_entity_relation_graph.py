import streamlit as st
import requests
from typing import List, Dict

def display_kag_entities_relations(entities: List[Dict], relations: List[Dict]):
    """显示KAG检索到的实体和关系图"""
    if not entities and not relations:
        return
    
    total_entities = len(entities)
    total_relations = len(relations)
    
    st.subheader("🔍 KAG检索到的实体和关系")
    st.write(f"检索到 {total_entities} 个实体, {total_relations} 个关系")
    
    try:
        from pyvis.network import Network
        import tempfile
        
        net = Network(
            height="600px",
            width="100%",
            bgcolor="#222222",
            font_color="white",
            directed=True
        )
        
        entity_type_colors = {
            "MilitaryUnit": "#FF6B6B",
            "TerrainFeature": "#4ECDC4",
            "Weapon": "#FFE66D",
            "Obstacle": "#95E1D3",
            "DefensePosition": "#F38181",
            "CombatPosition": "#AA96DA",
            "UnitOrganization": "#FCBAD3",
            "CombatTask": "#A8E6CF",
            "FireSupport": "#FFD3A5",
            "ObservationPost": "#FD9853",
            "KillZone": "#A8DADC",
            "ObstacleBelt": "#457B9D",
            "SupportPoint": "#E63946",
            "ApproachRoute": "#F1FAEE"
        }
        
        entity_map = {}
        for entity in entities:
            entity_id = entity.get("id", "")
            entity_name = entity.get("name", entity_id)
            entity_type = entity.get("type", "Unknown")
            color = entity_type_colors.get(entity_type, "#888888")
            
            title = f"<b>{entity_name}</b><br>类型: {entity_type}<br>ID: {entity_id}"
            properties = entity.get("properties", {})
            if properties:
                title += "<br>属性:"
                for key, value in list(properties.items())[:5]:
                    title += f"<br>  {key}: {value}"
            
            net.add_node(
                entity_id,
                label=entity_name[:20],
                title=title,
                color=color,
                size=20
            )
            entity_map[entity_id] = entity
        
        for relation in relations:
            source = relation.get("source", "")
            target = relation.get("target", "")
            relation_type = relation.get("type", "Unknown")
            
            if source in entity_map and target in entity_map:
                net.add_edge(
                    source,
                    target,
                    label=relation_type[:15],
                    title=relation_type,
                    color="#888888",
                    width=2
                )
        
        net.set_options("""
        {
          "physics": {
            "enabled": true,
            "barnesHut": {
              "gravitationalConstant": -2000,
              "centralGravity": 0.1,
              "springLength": 200,
              "springConstant": 0.04,
              "damping": 0.09
            },
            "stabilization": {
              "iterations": 100
            }
          },
          "interaction": {
            "hover": true,
            "tooltipDelay": 200,
            "zoomView": true,
            "dragView": true
          }
        }
        """)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as html_file:
            net.save_graph(html_file.name)
            html_path = html_file.name
        
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            
            st.components.v1.html(html_content, height=650, scrolling=True)
        finally:
            try:
                import os
                os.unlink(html_path)
            except:
                pass

    except ImportError:
        st.error("pyvis库未安装，请运行: pip install pyvis")
        st.code("pip install pyvis", language="bash")
    except Exception as e:
        st.error(f"生成可视化失败: {e}")
        import traceback
        st.code(traceback.format_exc())

def render_entity_relation_graph_tab(api_url: str):
    """渲染实体-关系图标签页"""
    st.header("🔍 实体-关系图可视化")
    st.markdown("从checkpoint文件中加载知识图谱，可视化实体和关系。")
    
    if "kg_checkpoint_path" not in st.session_state:
        st.session_state.kg_checkpoint_path = ""
    if "kg_entities" not in st.session_state:
        st.session_state.kg_entities = []
    if "kg_relations" not in st.session_state:
        st.session_state.kg_relations = []
    if "kg_search_term" not in st.session_state:
        st.session_state.kg_search_term = ""
    if "kg_entity_filter" not in st.session_state:
        st.session_state.kg_entity_filter = "全部"
    if "kg_relation_filter" not in st.session_state:
        st.session_state.kg_relation_filter = "全部"
    if "selected_node" not in st.session_state:
        st.session_state.selected_node = None

    col1, col2 = st.columns([3, 1])
    with col1:
        checkpoint_path = st.text_input(
            "Checkpoint文件路径",
            value=st.session_state.kg_checkpoint_path,
            placeholder="例如: f:/AIgen/result/checkpoint/xxx.json",
            key="kg_checkpoint_input"
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        load_button = st.button("📂 加载Checkpoint", type="primary", use_container_width=True)

    if load_button and checkpoint_path.strip():
        st.session_state.kg_checkpoint_path = checkpoint_path.strip()
        with st.spinner("正在加载checkpoint文件..."):
            try:
                with open(checkpoint_path.strip(), "r", encoding="utf-8") as f:
                    checkpoint_data = f.read()
                
                import json
                checkpoint_json = json.loads(checkpoint_data)
                
                entities = []
                relations = []
                
                if isinstance(checkpoint_json, dict):
                    if "entities" in checkpoint_json:
                        entities = checkpoint_json["entities"]
                    if "relations" in checkpoint_json:
                        relations = checkpoint_json["relations"]
                    
                    if not entities and not relations:
                        for key, value in checkpoint_json.items():
                            if isinstance(value, dict):
                                if "nodes" in value or "entities" in value:
                                    entities.extend(value.get("nodes", value.get("entities", [])))
                                if "edges" in value or "relations" in value:
                                    relations.extend(value.get("edges", value.get("relations", [])))
                elif isinstance(checkpoint_json, list):
                    for item in checkpoint_json:
                        if isinstance(item, dict):
                            if "nodes" in item or "entities" in item:
                                entities.extend(item.get("nodes", item.get("entities", [])))
                            if "edges" in item or "relations" in item:
                                relations.extend(item.get("edges", item.get("relations", [])))
                
                st.session_state.kg_entities = entities if entities else []
                st.session_state.kg_relations = relations if relations else []
                st.success(f"成功加载 {len(st.session_state.kg_entities)} 个实体和 {len(st.session_state.kg_relations)} 个关系")
                st.rerun()
            except FileNotFoundError:
                st.error(f"文件不存在: {checkpoint_path.strip()}")
            except json.JSONDecodeError as e:
                st.error(f"JSON解析失败: {e}")
            except Exception as e:
                st.error(f"加载失败: {e}")

    if st.session_state.kg_entities or st.session_state.kg_relations:
        st.markdown("---")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            search_term = st.text_input(
                "🔍 搜索实体",
                value=st.session_state.kg_search_term,
                placeholder="输入实体名称进行搜索...",
                key="kg_search_input"
            )
            if search_term != st.session_state.kg_search_term:
                st.session_state.kg_search_term = search_term
                st.rerun()
        
        with col2:
            entity_types = ["全部"] + sorted(list(set(e.get("type", "Unknown") for e in st.session_state.kg_entities)))
            entity_filter = st.selectbox(
                "筛选实体类型",
                options=entity_types,
                index=entity_types.index(st.session_state.kg_entity_filter) if st.session_state.kg_entity_filter in entity_types else 0,
                key="kg_entity_filter_select"
            )
            if entity_filter != st.session_state.kg_entity_filter:
                st.session_state.kg_entity_filter = entity_filter
                st.rerun()
        
        with col3:
            relation_types = ["全部"] + sorted(list(set(r.get("type", "Unknown") for r in st.session_state.kg_relations)))
            relation_filter = st.selectbox(
                "筛选关系类型",
                options=relation_types,
                index=relation_types.index(st.session_state.kg_relation_filter) if st.session_state.kg_relation_filter in relation_types else 0,
                key="kg_relation_filter_select"
            )
            if relation_filter != st.session_state.kg_relation_filter:
                st.session_state.kg_relation_filter = relation_filter
                st.rerun()

        filtered_entities = st.session_state.kg_entities
        filtered_relations = st.session_state.kg_relations
        
        if st.session_state.kg_entity_filter != "全部":
            filtered_entities = [e for e in filtered_entities if e.get("type") == st.session_state.kg_entity_filter]
        
        if st.session_state.kg_relation_filter != "全部":
            filtered_relations = [r for r in filtered_relations if r.get("type") == st.session_state.kg_relation_filter]
        
        if st.session_state.kg_search_term:
            search_term_lower = st.session_state.kg_search_term.lower()
            filtered_entities = [e for e in filtered_entities if st.session_state.kg_search_term.lower() in e.get("name", "").lower()]
            
            entity_ids = {e.get("id") for e in filtered_entities}
            filtered_relations = [r for r in filtered_relations if r.get("source") in entity_ids or r.get("target") in entity_ids]

        if filtered_entities or filtered_relations:
            st.subheader(f"📊 可视化 ({len(filtered_entities)} 个实体, {len(filtered_relations)} 个关系)")
            
            try:
                from pyvis.network import Network
                import tempfile
                import os
                
                net = Network(
                    height="600px",
                    width="100%",
                    bgcolor="#222222",
                    font_color="white",
                    directed=True
                )
                
                entity_type_colors = {
                    "MilitaryUnit": "#FF6B6B",
                    "TerrainFeature": "#4ECDC4",
                    "Weapon": "#FFE66D",
                    "Obstacle": "#95E1D3",
                    "DefensePosition": "#F38181",
                    "CombatPosition": "#AA96DA",
                    "UnitOrganization": "#FCBAD3",
                    "CombatTask": "#A8E6CF",
                    "FireSupport": "#FFD3A5",
                    "ObservationPost": "#FD9853",
                    "KillZone": "#A8DADC",
                    "ObstacleBelt": "#457B9D",
                    "SupportPoint": "#E63946",
                    "ApproachRoute": "#F1FAEE"
                }

                entity_map = {}
                for entity in filtered_entities:
                    entity_id = entity.get("id", "")
                    entity_name = entity.get("name", entity_id)
                    entity_type = entity.get("type", "Unknown")
                    color = entity_type_colors.get(entity_type, "#888888")
                    
                    title = f"<b>{entity_name}</b><br>类型: {entity_type}<br>ID: {entity_id}"
                    properties = entity.get("properties", {})
                    if properties:
                        title += "<br>属性:"
                        for key, value in list(properties.items())[:5]:
                            title += f"<br>  {key}: {value}"
                    
                    node_color = "#FFD700" if st.session_state.kg_search_term and st.session_state.kg_search_term.lower() in entity_name.lower() else color
                    
                    net.add_node(
                        entity_id,
                        label=entity_name[:20],
                        title=title,
                        color=node_color,
                        size=20
                    )
                    entity_map[entity_id] = entity

                for relation in filtered_relations:
                    source = relation.get("source", "")
                    target = relation.get("target", "")
                    relation_type = relation.get("type", "Unknown")
                    
                    if source in entity_map and target in entity_map:
                        net.add_edge(
                            source,
                            target,
                            label=relation_type[:15],
                            title=relation_type,
                            color="#888888",
                            width=2
                        )

                net.set_options("""
                {
                  "physics": {
                    "enabled": true,
                    "barnesHut": {
                      "gravitationalConstant": -2000,
                      "centralGravity": 0.1,
                      "springLength": 200,
                      "springConstant": 0.04,
                      "damping": 0.09
                    },
                    "stabilization": {
                      "iterations": 100
                    }
                  },
                  "interaction": {
                    "hover": true,
                    "tooltipDelay": 200,
                    "zoomView": true,
                    "dragView": true
                  }
                }
                """)

                with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as html_file:
                    net.save_graph(html_file.name)
                    html_path = html_file.name
                
                try:
                    with open(html_path, "r", encoding="utf-8") as f:
                        html_content = f.read()
                    
                    st.components.v1.html(html_content, height=650, scrolling=True)
                finally:
                    try:
                        os.unlink(html_path)
                    except:
                        pass

            except ImportError:
                st.error("pyvis库未安装，请运行: pip install pyvis")
                st.code("pip install pyvis", language="bash")
            except Exception as e:
                st.error(f"生成可视化失败: {e}")
                import traceback
                st.code(traceback.format_exc())

            if filtered_entities or filtered_relations:
                st.markdown("---")
                st.subheader("节点和关系对应的原文")
                
                def extract_source_text(item, item_type="节点"):
                    source_texts = []
                    properties = item.get("properties", {})
                    
                    text_fields = ["desc", "description", "content", "text", "ruleContent", "ruleName"]
                    
                    for field in text_fields:
                        if field in properties:
                            value = properties[field]
                            if value and isinstance(value, str) and value.strip():
                                source_texts.append({
                                    "field": field,
                                    "text": value
                                })
                    
                    if not source_texts:
                        for key, value in properties.items():
                            if isinstance(value, str) and len(value) > 10:
                                source_texts.append({
                                    "field": key,
                                    "text": value
                                })
                    
                    return source_texts
                
                if filtered_entities:
                    with st.expander(f"📝 节点原文 ({len(filtered_entities)} 个)", expanded=False):
                        for idx, entity in enumerate(filtered_entities, 1):
                            entity_name = entity.get("name", entity.get("id", f"节点{idx}"))
                            entity_type = entity.get("type", "Unknown")
                            source_texts = extract_source_text(entity, "节点")
                            
                            if source_texts:
                                st.markdown(f"**{idx}. {entity_name}** ({entity_type})")
                                for source_info in source_texts:
                                    field_name = source_info["field"]
                                    text = source_info["text"]
                                    if len(text) > 500:
                                        preview_text = text[:100].replace("\n", " ")
                                        with st.expander(f"  - {field_name}: {preview_text}...", expanded=False):
                                            st.text_area(
                                                f"{field_name} 原文",
                                                value=text,
                                                height=min(200, max(100, len(text) // 10)),
                                                key=f"node_{idx}_{field_name}",
                                                label_visibility="collapsed"
                                            )
                                    else:
                                        st.markdown(f"  - **{field_name}**:")
                                        st.text(text)
                                st.markdown("---")
                            else:
                                st.markdown(f"**{idx}. {entity_name}** ({entity_type}) - 无原文信息")
                                st.markdown("---")
                
                if filtered_relations:
                    with st.expander(f"🔗 关系原文 ({len(filtered_relations)} 个)", expanded=False):
                        for idx, relation in enumerate(filtered_relations, 1):
                            source_id = relation.get("source", "")
                            target_id = relation.get("target", "")
                            relation_type = relation.get("type", "Unknown")
                            
                            source_entity = next((e for e in filtered_entities if e.get("id") == source_id), None)
                            target_entity = next((e for e in filtered_entities if e.get("id") == target_id), None)
                            
                            source_name = source_entity.get("name", source_id) if source_entity else source_id
                            target_name = target_entity.get("name", target_id) if target_entity else target_id
                            
                            source_texts = extract_source_text(relation, "关系")
                            
                            if source_texts:
                                st.markdown(f"**{idx}. {source_name} --[{relation_type}]--> {target_name}**")
                                for source_info in source_texts:
                                    field_name = source_info["field"]
                                    text = source_info["text"]
                                    if len(text) > 500:
                                        preview_text = text[:100].replace("\n", " ")
                                        with st.expander(f"  - {field_name}: {preview_text}...", expanded=False):
                                            st.text_area(
                                                f"{field_name} 原文",
                                                value=text,
                                                height=min(200, max(100, len(text) // 10)),
                                                key=f"relation_{idx}_{field_name}",
                                                label_visibility="collapsed"
                                            )
                                    else:
                                        st.markdown(f"  - **{field_name}**:")
                                        st.text(text)
                                st.markdown("---")
                            else:
                                st.markdown(f"**{idx}. {source_name} --[{relation_type}]--> {target_name}** - 无原文信息")
                                st.markdown("---")

            if st.session_state.selected_node:
                st.markdown("---")
                st.subheader("节点详情")
                node_data = st.session_state.selected_node
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.write("**ID**:", node_data.get("id", "N/A"))
                    st.write("**名称**:", node_data.get("name", "N/A"))
                    st.write("**类型**:", node_data.get("type", "N/A"))
                with col2:
                    st.write("**属性**:")
                    st.json(node_data.get("properties", {}))
    
        else:
            st.info("没有数据可显示。请调整筛选条件或确保checkpoint文件存在。")
    else:
        st.info("请先加载checkpoint文件")
