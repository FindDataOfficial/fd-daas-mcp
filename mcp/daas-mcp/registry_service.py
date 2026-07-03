"""
Registry query service for daas-mcp.

Query layer over SQLAlchemy models — search, detail, categories, list.
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import cast, func, or_, select, String

from models import (
    DaasFunction,
    DaasFunctionColumn,
    DaasSource,
    Category,
    DatasourceForm,
    DatasourceSection,
    DatasourceCollection,
    DatasourceCollectionItem,
    Entity,
    EntityDatasourceLink,
)


# Routing-grammar helpers for entity coverage. The seed (seed_external_mcps)
# writes section `instruction` strings as `mcp=<mcp> tool=<tool>
# [param=<key>=<value>]*`. <ask-agent> marks a value the agent must supply.
_ROUTING_RE = re.compile(r"^mcp=(\S+)\s+tool=(\S+)(?:\s.*)?$")
# Param keys that carry an entity identifier — substituting
# identifier_in_source into these yields a directly runnable instruction.
# Other <ask-agent> params (params_json, selector, date, detail, ...) are left.
_IDENT_PARAM_RE = re.compile(
    r"^(ticker_or_cik|ticker_or_name|ticker_or_code|ticker|symbol|code)$"
)


class RegistryService:
    """Query orchestration for DAAS function metadata."""

    def __init__(self, session: Session):
        self._session = session

    def list_sources(self) -> list[dict]:
        sources = self._session.query(DaasSource).order_by(DaasSource.name).all()
        result = []
        for s in sources:
            cnt = (
                self._session.query(func.count(DaasFunction.id))
                .filter(DaasFunction.source_id == s.id)
                .scalar()
            )
            d = s.to_dict()
            d["function_count"] = cnt
            result.append(d)
        return result

    def search_functions(self, query: str, source: Optional[str] = None, limit: int = 20) -> list[dict]:
        q = f"%{query}%"
        q_obj = (
            self._session.query(DaasFunction)
            .join(DaasSource)
            .filter(
                or_(
                    DaasFunction.name.like(q),
                    DaasFunction.category.like(q),
                    DaasFunction.description.like(q),
                )
            )
        )
        if source:
            q_obj = q_obj.filter(DaasSource.name == source)
        results = q_obj.order_by(DaasSource.name, DaasFunction.name).limit(limit).all()
        return [f.to_dict() for f in results]

    def get_function_detail(self, name: str) -> Optional[dict]:
        func = self._session.query(DaasFunction).filter(DaasFunction.name == name).first()
        if func is None:
            return None
        return func.to_dict()

    def list_categories(self, source: Optional[str] = None) -> list[dict]:
        q = (
            self._session.query(
                DaasSource.name.label("source_name"),
                DaasFunction.category,
                func.count(DaasFunction.id).label("cnt"),
            )
            .join(DaasFunction.source)
        )
        if source:
            q = q.filter(DaasSource.name == source)
        rows = (
            q.group_by(DaasSource.name, DaasFunction.category)
            .order_by(DaasSource.name, func.count(DaasFunction.id).desc())
            .all()
        )
        return [
            {"source": row.source_name, "category": row.category, "count": row.cnt}
            for row in rows
        ]

    # ════════════════════════════════════════════════════════════
    # Management domain — categories, datasource CRUD, forms/sections,
    # collections, multi-level search (additive to the read API above)
    # ════════════════════════════════════════════════════════════

    # --- Category tree -----------------------------------------------------

    _MAX_DEPTH = 100  # ponytail: cycle guard ceiling; trees are small

    def create_category(
        self,
        name: str,
        label: Optional[str] = None,
        parent_id: Optional[int] = None,
        sort_order: Optional[int] = None,
    ) -> dict:
        if parent_id is not None:
            parent = self._session.get(Category, parent_id)
            if parent is None:
                raise ValueError(f"Parent category id {parent_id} not found")
        cat = Category(name=name, label=label or name, parent_id=parent_id, sort_order=sort_order)
        self._session.add(cat)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return cat.to_dict()

    def _ancestor_ids(self, category_id: int) -> set[int]:
        """Walk parent chain; cycle-safe via visited set + depth cap."""
        ids: set[int] = set()
        cur = category_id
        depth = 0
        while cur is not None and depth < self._MAX_DEPTH:
            if cur in ids:
                break  # cycle
            ids.add(cur)
            cat = self._session.get(Category, cur)
            if cat is None:
                break
            cur = cat.parent_id
            depth += 1
        return ids

    def move_category(self, category_id: int, parent_id: Optional[int]) -> dict:
        cat = self._session.get(Category, category_id)
        if cat is None:
            raise ValueError(f"Category id {category_id} not found")
        if parent_id is not None:
            if parent_id == category_id:
                raise ValueError("A category cannot be its own parent")
            parent = self._session.get(Category, parent_id)
            if parent is None:
                raise ValueError(f"Parent category id {parent_id} not found")
            # Reject moving into own descendant subtree (would create a cycle)
            if parent_id in self._descendant_ids(category_id):
                raise ValueError("Cannot move a category into its own descendant subtree")
        cat.parent_id = parent_id
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return cat.to_dict()

    def _descendant_ids(self, category_id: int) -> set[int]:
        """BFS down the subtree; cycle-safe via visited set + depth cap."""
        result: set[int] = set()
        frontier = [category_id]
        depth = 0
        while frontier and depth < self._MAX_DEPTH:
            nxt: list[int] = []
            for cid in frontier:
                children = (
                    self._session.query(Category.id)
                    .filter(Category.parent_id == cid)
                    .all()
                )
                for (child_id,) in children:
                    if child_id in result:
                        continue
                    result.add(child_id)
                    nxt.append(child_id)
            frontier = nxt
            depth += 1
        return result

    def get_subtree_ids(self, category_id: int) -> list[int]:
        """Return the category + all descendant ids. Cycle-safe."""
        return [category_id, *sorted(self._descendant_ids(category_id))]

    def delete_category(self, category_id: int) -> dict:
        cat = self._session.get(Category, category_id)
        if cat is None:
            raise ValueError(f"Category id {category_id} not found")
        child_count = (
            self._session.query(func.count(Category.id))
            .filter(Category.parent_id == category_id)
            .scalar()
        )
        if child_count:
            raise ValueError(
                f"Category '{cat.name}' has {child_count} child categories; "
                "move or delete them first"
            )
        # Orphan assigned datasources to root level (category_id = NULL)
        self._session.query(DaasSource).filter(DaasSource.category_id == category_id).update(
            {DaasSource.category_id: None}
        )
        self._session.delete(cat)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return {"deleted": category_id}

    def get_category_tree(self, root_id: Optional[int] = None) -> list[dict]:
        if root_id is not None:
            roots = [self._session.get(Category, root_id)]
            roots = [r for r in roots if r is not None]
        else:
            roots = (
                self._session.query(Category)
                .filter(Category.parent_id.is_(None))
                .order_by(Category.sort_order.nulls_last(), Category.name)
                .all()
            )
        return [self._category_node(r) for r in roots]

    def _category_node(self, cat: Category) -> dict:
        d = cat.to_dict()
        d["datasource_count"] = (
            self._session.query(func.count(DaasSource.id))
            .filter(DaasSource.category_id == cat.id)
            .scalar()
        )
        children = sorted(
            (c for c in (cat.children or []) if c is not None),
            key=lambda c: (c.sort_order if c.sort_order is not None else 0, c.name),
        )
        d["children"] = [self._category_node(c) for c in children]
        return d

    def _category_path(self, category_id: Optional[int]) -> Optional[list[str]]:
        if category_id is None:
            return None
        path: list[str] = []
        cur = category_id
        depth = 0
        while cur is not None and depth < self._MAX_DEPTH:
            cat = self._session.get(Category, cur)
            if cat is None:
                break
            if cat.name in path:  # cycle guard
                break
            path.append(cat.name)
            cur = cat.parent_id
            depth += 1
        path.reverse()
        return path

    # --- Datasource CRUD ---------------------------------------------------

    def create_datasource(
        self,
        name: str,
        label: str,
        description: Optional[str] = None,
        url: Optional[str] = None,
        config: Optional[dict] = None,
        category_id: Optional[int] = None,
        enabled: bool = True,
    ) -> dict:
        existing = self._session.query(DaasSource).filter(DaasSource.name == name).first()
        if existing is not None:
            raise ValueError(f"Datasource '{name}' already exists")
        if category_id is not None:
            if self._session.get(Category, category_id) is None:
                raise ValueError(f"Category id {category_id} not found")
        src = DaasSource(
            name=name,
            label=label,
            description=description,
            url=url,
            config=config,
            category_id=category_id,
            enabled=enabled,
        )
        self._session.add(src)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return self._source_detail(src)

    def update_datasource(
        self,
        name: Optional[str] = None,
        datasource_id: Optional[int] = None,
        label: Optional[str] = None,
        description: Optional[str] = None,
        url: Optional[str] = None,
        config: Optional[dict] = None,
        enabled: Optional[bool] = None,
        category_id: Optional[int] = None,
        clear_category: bool = False,
    ) -> dict:
        src = self._resolve_source(name, datasource_id)
        if src is None:
            raise ValueError("Datasource not found")
        if label is not None:
            src.label = label
        if description is not None:
            src.description = description
        if url is not None:
            src.url = url
        if config is not None:
            src.config = config
        if enabled is not None:
            src.enabled = enabled
        if clear_category:
            src.category_id = None
        elif category_id is not None:
            if self._session.get(Category, category_id) is None:
                raise ValueError(f"Category id {category_id} not found")
            src.category_id = category_id
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return self._source_detail(src)

    def delete_datasource(
        self, name: Optional[str] = None, datasource_id: Optional[int] = None
    ) -> dict:
        src = self._resolve_source(name, datasource_id)
        if src is None:
            raise ValueError("Datasource not found")
        deleted = src.name
        # FK ON DELETE CASCADE handles forms/sections/collection items
        self._session.delete(src)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return {"deleted": deleted}

    def _resolve_source(
        self, name: Optional[str], datasource_id: Optional[int]
    ) -> Optional[DaasSource]:
        if datasource_id is not None:
            return self._session.get(DaasSource, datasource_id)
        if name is not None:
            return self._session.query(DaasSource).filter(DaasSource.name == name).first()
        return None

    def _source_detail(self, src: DaasSource) -> dict:
        d = src.to_dict()
        d["id"] = src.id
        d["category_path"] = self._category_path(src.category_id)
        d["form_count"] = (
            self._session.query(func.count(DatasourceForm.id))
            .filter(DatasourceForm.source_id == src.id)
            .scalar()
        )
        return d

    # --- Forms & sections --------------------------------------------------

    def add_form(
        self,
        source_name: str,
        form_type: str,
        label: Optional[str] = None,
    ) -> dict:
        src = self._resolve_source(source_name, None)
        if src is None:
            raise ValueError(f"Datasource '{source_name}' not found")
        existing = (
            self._session.query(DatasourceForm)
            .filter(DatasourceForm.source_id == src.id, DatasourceForm.form_type == form_type)
            .first()
        )
        if existing is not None:
            raise ValueError(
                f"Form '{form_type}' already exists for datasource '{source_name}'"
            )
        form = DatasourceForm(source_id=src.id, form_type=form_type, label=label)
        self._session.add(form)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return form.to_dict()

    def add_section(
        self,
        form_id: int,
        section_name: str,
        instruction: Optional[str] = None,
        sort_order: Optional[int] = None,
    ) -> dict:
        form = self._session.get(DatasourceForm, form_id)
        if form is None:
            raise ValueError(f"Form id {form_id} not found")
        existing = (
            self._session.query(DatasourceSection)
            .filter(
                DatasourceSection.form_id == form_id,
                DatasourceSection.section_name == section_name,
            )
            .first()
        )
        if existing is not None:
            raise ValueError(
                f"Section '{section_name}' already exists for form id {form_id}"
            )
        sec = DatasourceSection(
            form_id=form_id,
            section_name=section_name,
            instruction=instruction,
            sort_order=sort_order,
        )
        self._session.add(sec)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return sec.to_dict()

    def list_forms(self, source_name: str) -> list[dict]:
        src = self._resolve_source(source_name, None)
        if src is None:
            raise ValueError(f"Datasource '{source_name}' not found")
        forms = (
            self._session.query(DatasourceForm)
            .filter(DatasourceForm.source_id == src.id)
            .order_by(DatasourceForm.form_type)
            .all()
        )
        return [f.to_dict() for f in forms]

    def _resolve_section(
        self, source_id: int, section_name: str
    ) -> Optional[DatasourceSection]:
        return (
            self._session.query(DatasourceSection)
            .join(DatasourceForm)
            .filter(
                DatasourceForm.source_id == source_id,
                DatasourceSection.section_name == section_name,
            )
            .first()
        )

    # --- Collections -------------------------------------------------------

    def create_collection(self, name: str, description: Optional[str] = None) -> dict:
        existing = (
            self._session.query(DatasourceCollection)
            .filter(DatasourceCollection.name == name)
            .first()
        )
        if existing is not None:
            raise ValueError(f"Collection '{name}' already exists")
        coll = DatasourceCollection(name=name, description=description)
        self._session.add(coll)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return coll.to_dict()

    def add_to_collection(
        self,
        collection_name: str,
        source_name: str,
        section_name: Optional[str] = None,
    ) -> dict:
        coll = (
            self._session.query(DatasourceCollection)
            .filter(DatasourceCollection.name == collection_name)
            .first()
        )
        if coll is None:
            raise ValueError(f"Collection '{collection_name}' not found")
        src = self._resolve_source(source_name, None)
        if src is None:
            raise ValueError(f"Datasource '{source_name}' not found")
        section_id: Optional[int] = None
        if section_name is not None:
            sec = self._resolve_section(src.id, section_name)
            if sec is None:
                raise ValueError(
                    f"Section '{section_name}' not found for datasource '{source_name}'"
                )
            section_id = sec.id
        dup = (
            self._session.query(DatasourceCollectionItem)
            .filter(
                DatasourceCollectionItem.collection_id == coll.id,
                DatasourceCollectionItem.source_id == src.id,
                DatasourceCollectionItem.section_id.is_(section_id)
                if section_id is None
                else DatasourceCollectionItem.section_id == section_id,
            )
            .first()
        )
        if dup is not None:
            raise ValueError("Item already in collection")
        # Append at end: sort_order = max(existing) + 1, or 0 if empty.
        next_order = (
            self._session.query(func.coalesce(func.max(DatasourceCollectionItem.sort_order), -1))
            .filter(DatasourceCollectionItem.collection_id == coll.id)
            .scalar()
        ) + 1
        item = DatasourceCollectionItem(
            collection_id=coll.id,
            source_id=src.id,
            section_id=section_id,
            sort_order=next_order,
        )
        self._session.add(item)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return item.to_dict()

    def list_collection(self, collection_name: str) -> dict:
        coll = (
            self._session.query(DatasourceCollection)
            .filter(DatasourceCollection.name == collection_name)
            .first()
        )
        if coll is None:
            raise ValueError(f"Collection '{collection_name}' not found")
        items = (
            self._session.query(DatasourceCollectionItem)
            .filter(DatasourceCollectionItem.collection_id == coll.id)
            .order_by(DatasourceCollectionItem.sort_order, DatasourceCollectionItem.id)
            .all()
        )
        resolved = []
        for it in items:
            src = self._session.get(DaasSource, it.source_id)
            sec = self._session.get(DatasourceSection, it.section_id) if it.section_id else None
            resolved.append(
                {
                    "item_id": it.id,
                    "source_name": src.name if src else None,
                    "section_id": it.section_id,
                    "section_name": sec.section_name if sec else None,
                    "instruction": sec.instruction if sec else None,
                    "sort_order": it.sort_order,
                }
            )
        return {"collection": coll.to_dict(), "items": resolved}

    def remove_from_collection(
        self,
        collection_name: str,
        source_name: str,
        section_name: Optional[str] = None,
    ) -> dict:
        coll = (
            self._session.query(DatasourceCollection)
            .filter(DatasourceCollection.name == collection_name)
            .first()
        )
        if coll is None:
            raise ValueError(f"Collection '{collection_name}' not found")
        src = self._resolve_source(source_name, None)
        if src is None:
            raise ValueError(f"Datasource '{source_name}' not found")
        section_id: Optional[int] = None
        if section_name is not None:
            sec = self._resolve_section(src.id, section_name)
            section_id = sec.id if sec else None
        q = self._session.query(DatasourceCollectionItem).filter(
            DatasourceCollectionItem.collection_id == coll.id,
            DatasourceCollectionItem.source_id == src.id,
        )
        if section_name is not None:
            q = q.filter(DatasourceCollectionItem.section_id == section_id)
        else:
            q = q.filter(DatasourceCollectionItem.section_id.is_(None))
        item = q.first()
        if item is None:
            raise ValueError("Item not found in collection")
        self._session.delete(item)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return {"removed": item.id}

    def list_collections(self) -> list[dict]:
        """All collections with item counts. Used by the dashboard picker."""
        colls = (
            self._session.query(DatasourceCollection)
            .order_by(DatasourceCollection.name)
            .all()
        )
        return [c.to_dict() for c in colls]

    def rename_collection(self, old_name: str, new_name: str) -> dict:
        coll = (
            self._session.query(DatasourceCollection)
            .filter(DatasourceCollection.name == old_name)
            .first()
        )
        if coll is None:
            raise ValueError(f"Collection '{old_name}' not found")
        if new_name != old_name:
            clash = (
                self._session.query(DatasourceCollection)
                .filter(DatasourceCollection.name == new_name)
                .first()
            )
            if clash is not None:
                raise ValueError(f"Collection '{new_name}' already exists")
        coll.name = new_name
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return coll.to_dict()

    def update_collection(
        self,
        name: str,
        new_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict:
        """Partially update a collection's name and/or description.

        At least one of `new_name` / `description` must be provided; omitted
        fields are left unchanged. When `new_name` is set and differs from the
        current name, the new name must be unique (clash raises ValueError).
        Raises ValueError if the collection is not found or no fields were
        provided. Preserves all `datasource_collection_items` rows (they
        reference by collection_id, not by name). `updated_at` is bumped by
        the model's `onupdate`.
        """
        if new_name is None and description is None:
            raise ValueError("At least one of new_name or description is required")
        coll = (
            self._session.query(DatasourceCollection)
            .filter(DatasourceCollection.name == name)
            .first()
        )
        if coll is None:
            raise ValueError(f"Collection '{name}' not found")
        if new_name is not None and new_name != name:
            clash = (
                self._session.query(DatasourceCollection)
                .filter(DatasourceCollection.name == new_name)
                .first()
            )
            if clash is not None:
                raise ValueError(f"Collection '{new_name}' already exists")
            coll.name = new_name
        # An explicit empty string clears the description; None leaves it unchanged.
        if description is not None:
            coll.description = description
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return coll.to_dict()

    def delete_collection(self, name: str) -> dict:
        coll = (
            self._session.query(DatasourceCollection)
            .filter(DatasourceCollection.name == name)
            .first()
        )
        if coll is None:
            raise ValueError(f"Collection '{name}' not found")
        # FK ON DELETE CASCADE handles datasource_collection_items.
        self._session.delete(coll)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return {"deleted": name}

    def reorder_collection_items(
        self, collection_name: str, ordered_item_ids: list[int]
    ) -> dict:
        """Rewrite sort_order for items in `collection_name` to match the
        given ordered list. Rejects the whole reorder if any id isn't in
        the collection or if the id set doesn't exactly match.
        """
        coll = (
            self._session.query(DatasourceCollection)
            .filter(DatasourceCollection.name == collection_name)
            .first()
        )
        if coll is None:
            raise ValueError(f"Collection '{collection_name}' not found")
        items = (
            self._session.query(DatasourceCollectionItem)
            .filter(DatasourceCollectionItem.collection_id == coll.id)
            .all()
        )
        existing_ids = {it.id for it in items}
        requested_ids = list(ordered_item_ids)
        unknown = set(requested_ids) - existing_ids
        if unknown:
            raise ValueError(
                f"Items {sorted(unknown)} are not in collection '{collection_name}'"
            )
        if set(requested_ids) != existing_ids:
            missing = existing_ids - set(requested_ids)
            raise ValueError(
                f"Reorder must include every collection item; missing: {sorted(missing)}"
            )
        by_id = {it.id: it for it in items}
        for new_order, item_id in enumerate(requested_ids):
            by_id[item_id].sort_order = new_order
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return {"collection": collection_name, "order": requested_ids}

    # --- Multi-level search ------------------------------------------------

    def search_datasources(
        self,
        category_id: Optional[int] = None,
        include_subtree: bool = True,
        source_name: Optional[str] = None,
        form: Optional[str] = None,
        section: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        limit = min(max(limit, 1), 500)
        expand = (form is not None) or (section is not None) or (query is not None)

        q = self._session.query(DaasSource)
        if category_id is not None:
            cat_ids = self.get_subtree_ids(category_id) if include_subtree else [category_id]
            q = q.filter(DaasSource.category_id.in_(cat_ids))
        if source_name is not None:
            q = q.filter(DaasSource.name == source_name)
        if query is not None:
            like = f"%{query}%"
            # Free-text across source label/description/name OR any form label
            # OR any section name/instruction. Sources matching only via a
            # form/section must still be included, so expand the source set
            # with sources that own a matching form/section.
            like_q = f"%{query}%"
            matching_source_ids_via_form = (
                select(DatasourceForm.source_id)
                .where(DatasourceForm.label.like(like_q))
                .distinct()
            )
            matching_source_ids_via_section = (
                select(DatasourceForm.source_id)
                .join(DatasourceSection, DatasourceSection.form_id == DatasourceForm.id)
                .where(
                    or_(
                        DatasourceSection.section_name.like(like_q),
                        DatasourceSection.instruction.like(like_q),
                    )
                )
                .distinct()
            )
            q = q.filter(
                or_(
                    DaasSource.label.like(like),
                    DaasSource.description.like(like),
                    DaasSource.name.like(like),
                    DaasSource.id.in_(matching_source_ids_via_form),
                    DaasSource.id.in_(matching_source_ids_via_section),
                )
            )
        sources = q.order_by(DaasSource.name).limit(limit).all()

        results = []
        for src in sources:
            if not expand:
                d = self._source_detail(src)
                results.append(d)
                continue
            # Expand forms/sections, applying form/section/query filters
            matched_forms = self._matching_forms(src, form, section, query)
            if form is not None or section is not None:
                # Drill filters: only keep sources that actually match
                if not matched_forms and (form is not None or section is not None):
                    continue
            d = self._source_detail(src)
            d["forms"] = matched_forms if matched_forms else []
            results.append(d)
        return results

    def _matching_forms(
        self,
        src: DaasSource,
        form: Optional[str],
        section: Optional[str],
        query: Optional[str],
    ) -> list[dict]:
        q = self._session.query(DatasourceForm).filter(DatasourceForm.source_id == src.id)
        if form is not None:
            q = q.filter(DatasourceForm.form_type == form)
        forms = q.order_by(DatasourceForm.form_type).all()
        out = []
        like = f"%{query}%" if query else None
        for f in forms:
            secs_q = self._session.query(DatasourceSection).filter(
                DatasourceSection.form_id == f.id
            )
            if section is not None:
                secs_q = secs_q.filter(DatasourceSection.section_name.like(f"%{section}%"))
            secs = secs_q.order_by(DatasourceSection.sort_order.nulls_last()).all()
            # Free-text query: include form if label matches, or any section matches
            form_label_match = like and f.label and like.lower() in f.label.lower()
            if like and not form_label_match:
                secs = [
                    s
                    for s in secs
                    if (s.section_name and like.lower() in s.section_name.lower())
                    or (s.instruction and like.lower() in s.instruction.lower())
                ]
            if section is not None and not secs and form is None:
                continue
            fd = {
                "id": f.id,
                "form_type": f.form_type,
                "label": f.label,
                "sections": [s.to_dict() for s in secs],
            }
            out.append(fd)
        return out

    # ════════════════════════════════════════════════════════════
    # Entity domain — stocks + countries, linked to daas `sources`
    # ════════════════════════════════════════════════════════════

    def search_entities(
        self, query: str, entity_type: Optional[str] = None, limit: int = 20
    ) -> list[dict]:
        """Case-insensitive substring match on name / ticker / code, plus
        a JSON-text LIKE on the aliases list. Returns up to `limit` hits."""
        limit = min(max(limit, 1), 100)
        like = f"%{query.lower()}%"
        q = self._session.query(Entity)
        if entity_type:
            q = q.filter(Entity.entity_type == entity_type)
        q = q.filter(
            or_(
                func.lower(Entity.name).like(like),
                func.lower(Entity.ticker).like(like),
                func.lower(Entity.code).like(like),
                cast(Entity.aliases, String).like(f"%{query}%"),
            )
        )
        rows = q.order_by(Entity.name).limit(limit).all()
        return [r.to_dict() for r in rows]

    def get_entity(self, entity_id: int) -> Optional[dict]:
        e = self._session.get(Entity, entity_id)
        return e.to_dict() if e is not None else None

    def list_entities(
        self,
        entity_type: Optional[str] = None,
        exchange: Optional[str] = None,
        country_code: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        limit = min(max(limit, 1), 500)
        offset = max(offset, 0)
        q = self._session.query(Entity)
        if entity_type:
            q = q.filter(Entity.entity_type == entity_type)
        if exchange:
            q = q.filter(Entity.exchange == exchange)
        if country_code:
            q = q.filter(Entity.country_code == country_code)
        total = q.count()
        rows = (
            q.order_by(Entity.entity_type, Entity.name)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "entities": [r.to_dict() for r in rows],
            "count": len(rows),
            "total": total,
            "offset": offset,
        }

    def get_entity_coverage(self, entity_id: int) -> dict:
        """For each datasource linked to the entity, return: identifier,
        available sections (with the routing instruction and an
        identifier-prefilled variant), and column count/list from
        `daas_function_columns` for that source. When the source has no
        registered `daas_functions` (external-MCP sources), return a
        `column_hint` naming the sibling MCP + tool so the caller can fetch
        columns via that MCP's get_function_info."""
        e = self._session.get(Entity, entity_id)
        if e is None:
            raise ValueError(f"Entity id {entity_id} not found")
        out = []
        for link in (e.links or []):
            src = link.source
            if src is None:
                continue
            forms = (
                self._session.query(DatasourceForm)
                .filter(DatasourceForm.source_id == src.id)
                .order_by(DatasourceForm.form_type)
                .all()
            )
            sections = []
            mcp_hint: Optional[str] = None
            tool_hint: Optional[str] = None
            for f in forms:
                secs = (
                    self._session.query(DatasourceSection)
                    .filter(DatasourceSection.form_id == f.id)
                    .order_by(DatasourceSection.sort_order.nulls_last())
                    .all()
                )
                for sec in secs:
                    instr = sec.instruction or ""
                    if mcp_hint is None:
                        m = _ROUTING_RE.match(instr)
                        if m:
                            mcp_hint, tool_hint = m.group(1), m.group(2)
                    sections.append(
                        {
                            "form_type": f.form_type,
                            "section_name": sec.section_name,
                            "instruction": instr,
                            "prefilled_instruction": self._substitute_identifier(
                                instr, link.identifier_in_source
                            ),
                        }
                    )
            cols = (
                self._session.query(DaasFunctionColumn)
                .join(DaasFunction)
                .filter(DaasFunction.source_id == src.id)
                .all()
            )
            d = {
                "source": src.name,
                "source_label": src.label,
                "identifier_in_source": link.identifier_in_source,
                "coverage": link.coverage,
                "sections": sections,
                "column_count": len(cols),
                "columns": [
                    {
                        "name": c.name,
                        "label": c.label,
                        "type": c.type,
                        "description": c.description,
                    }
                    for c in cols
                ],
            }
            if not cols and (mcp_hint or tool_hint):
                d["column_hint"] = {
                    "mcp": mcp_hint,
                    "tool": tool_hint,
                    "note": (
                        f"Columns live in {mcp_hint}; call its get_function_info "
                        f"for tool '{tool_hint}' to retrieve them."
                    ),
                }
            out.append(d)
        return {
            "entity_id": entity_id,
            "entity": e.to_dict(),
            "datasources": out,
            "count": len(out),
        }

    @staticmethod
    def _substitute_identifier(instruction: str, identifier: Optional[str]) -> str:
        """Replace <ask-agent> only in params whose key is an identifier key
        (ticker_or_cik, ticker_or_name, ticker_or_code, ticker, symbol, code).
        Other <ask-agent> params stay — the agent must still supply them."""
        if not instruction or not identifier:
            return instruction
        out: list[str] = []
        for token in instruction.split():
            if token.startswith("param="):
                kv = token[len("param="):]
                if "=" in kv:
                    key, val = kv.split("=", 1)
                    if val == "<ask-agent>" and _IDENT_PARAM_RE.match(key):
                        out.append(f"param={key}={identifier}")
                        continue
            out.append(token)
        return " ".join(out)

    def link_entity_datasource(
        self,
        entity_id: int,
        source_name: str,
        identifier_in_source: Optional[str] = None,
        coverage: str = "full",
        metadata: Optional[dict] = None,
    ) -> dict:
        if self._session.get(Entity, entity_id) is None:
            raise ValueError(f"Entity id {entity_id} not found")
        src = self._resolve_source(source_name, None)
        if src is None:
            raise ValueError(f"source '{source_name}' not found")
        link = (
            self._session.query(EntityDatasourceLink)
            .filter(
                EntityDatasourceLink.entity_id == entity_id,
                EntityDatasourceLink.source_id == src.id,
            )
            .first()
        )
        if link is None:
            link = EntityDatasourceLink(
                entity_id=entity_id,
                source_id=src.id,
                identifier_in_source=identifier_in_source,
                coverage=coverage,
                metadata_=metadata,
            )
            self._session.add(link)
        else:
            link.identifier_in_source = identifier_in_source
            link.coverage = coverage
            if metadata is not None:
                link.metadata_ = metadata
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return link.to_dict()

    def unlink_entity_datasource(self, entity_id: int, source_name: str) -> dict:
        src = self._resolve_source(source_name, None)
        if src is None:
            raise ValueError(f"source '{source_name}' not found")
        link = (
            self._session.query(EntityDatasourceLink)
            .filter(
                EntityDatasourceLink.entity_id == entity_id,
                EntityDatasourceLink.source_id == src.id,
            )
            .first()
        )
        if link is None:
            raise ValueError("link not found")
        deleted = link.id
        self._session.delete(link)
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return {"deleted": deleted}
